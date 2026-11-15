"""Authenticated HTTP opening shared by all tickets in an automation run."""

import asyncio
import re

import httpx

from app.automation.cancellation import cancellation_scope, check_cancelled, run_blocking
from app.automation.flows.flow_events import emit_step
from app.data.chamados_log import mark_cte_processed, read_processed_ctes
from app.infrastructure.chamados_postgres import CommunicationUnavailable
from app.infrastructure.pending_queue import access_key, cte_number, identity
from app.services.chamados_catalog import current_catalog
from app.services.execution_reports.models import ticket
from app.services.novelis_report_http import ReportDownloadError, authenticated, download_report

from . import ChamadoHttpError, prepare, submit_once, verify_ticket
from .outcomes import publish_result, record
from .payload import prepare_payload
from .report_lookup import existing_number, report_period
from .submissions import Submissions


class HttpChamadosSession:
    def __init__(self, cwd, config, emit, run_id, *, transport=None):
        self.cwd, self.config, self.emit, self.run_id = cwd, config, emit, run_id
        self.transport = transport
        self.client, self._context = None, None
        self._authentication_failed = False
        self._opened, self._reports, self._ledger = {}, {}, None
        self.submissions = Submissions(cwd, config)
        self.root = cwd / "runtime/novelis-http" / re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)
        self.staging = cwd / "captures/novelis-chamados-direto/http" / self.root.name

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        if self._context:
            await self._context.__aexit__(*exc)

    async def _client(self):
        if self._authentication_failed:
            raise ChamadoHttpError(
                "A autenticação HTTP deste lote falhou. Confira o acesso ao portal."
            )
        if self.client is None:
            context = authenticated(self.config, self.transport)
            try:
                self.client = await context.__aenter__()
            except (httpx.HTTPError, ReportDownloadError):
                self._authentication_failed = True
                raise
            self._context = context
            await emit_step(
                self.emit,
                self.run_id,
                "novelis.http.authenticated",
                "Novelis: sessão HTTP autenticada para a abertura dos chamados.",
            )
        return self.client

    async def _report(self, row, output, *, fresh=False):
        from app.automation.flows.novelis_relatorio.steps.novelis_relatorio_cte_xml import (
            NovelisRelatorioCteXmlFlow,
        )

        flow = NovelisRelatorioCteXmlFlow(self.cwd, None)
        period = report_period(row, flow._date_range(self.config))
        key = tuple(period.values())
        if fresh or key not in self._reports:
            await emit_step(
                self.emit,
                self.run_id,
                "novelis_relatorio.http_check",
                "Relatório Novelis: conferindo os chamados por HTTP.",
                {"querySource": "novelis", "cte": cte_number(row)},
            )
            info = await download_report(
                self.config, period, output / "consulta-novelis.xlsx", client=await self._client()
            )
            self._reports[key] = await run_blocking(flow._parse_excel, info["file"])
        return next(
            (
                str(hit["chamadoNumero"])
                for hit in self._reports[key]
                if access_key(hit) == access_key(row) and hit.get("chamadoNumero")
            ),
            "",
        )

    def _local_existing(self, row, config):
        if catalog := current_catalog(self.cwd):
            hits = catalog.opened_identities([row])
            if number := existing_number(hits, row):
                return number
        if self._ledger is None:
            self._ledger = read_processed_ctes(config.get("chamadosLogFile"))
        return existing_number([self._ledger.get(cte_number(row), {})], row)

    def _remember(self, row, config, number, status="aberto"):
        if catalog := current_catalog(self.cwd):
            catalog.record_processed(row, status, number)
            return True
        path = config.get("chamadosLogFile")
        if path:
            mark_cte_processed(
                path,
                row.get("filial"),
                row.get("serie"),
                row.get("documento"),
                status,
                number,
                access_key(row),
            )
            return True
        return False

    async def _reconcile(self, row, prepared, output, result):
        if number := await self._report(row, output, fresh=True):
            return await verify_ticket(
                await self._client(),
                number,
                cte_number(row),
                prepared.uploads,
                {**result, "confirmation_source": "portal_report"},
            )
        return result

    async def _send(self, row, prepared, output, result):
        attempted = False
        try:
            previous = await run_blocking(self.submissions.reserve, row, self.run_id)
            if previous:
                if previous.get("status") in {"confirmed", "duplicate"} and previous.get("number"):
                    return {**result, "status": "already_exists", "number": previous["number"]}
                reconciled = await self._reconcile(
                    row, prepared, output, {**result, "status": "indeterminate"}
                )
                if reconciled["status"] == "confirmed":
                    await run_blocking(self.submissions.finish, row, reconciled)
                    reconciled["status"] = "already_exists"
                return reconciled
            await emit_step(
                self.emit,
                self.run_id,
                "novelis.http.submit",
                "Novelis: enviando o chamado por HTTP.",
                {"cte": cte_number(row), "transport": "http"},
            )
            check_cancelled()
            attempted = True
            result = {
                **result,
                **await submit_once(await self._client(), prepared, cte_number(row)),
            }
            record(output / "result.json", result)
            await run_blocking(self.submissions.finish, row, result)
            if result["status"] == "indeterminate":
                result = await self._reconcile(row, prepared, output, result)
                await run_blocking(self.submissions.finish, row, result)
        except asyncio.CancelledError:
            confirmed = result.get("status") == "confirmed"
            status = "confirmed" if confirmed else "indeterminate"
            if not attempted:
                status = "cancelled_before_submit"
            result = {
                **result,
                "status": status,
                "submitted": attempted,
                "cancelled": True,
            }
            if confirmed:
                result["ticket"] = ticket(row, result["number"])
            record(output / "result.json", result)
            if attempted:
                await asyncio.to_thread(self.submissions.finish, row, result)
            else:
                # Cancellation is already requested. Finish this short cleanup outside the cancelled worker scope.
                await asyncio.to_thread(self.submissions.release, row, self.run_id)
            if confirmed:
                with cancellation_scope(None):
                    await publish_result(self.emit, self.run_id, result)
            raise
        return result

    async def open(self, row, config, *, send=True):
        check_cancelled()
        cte = cte_number(row)
        if not cte or not access_key(row):
            raise ChamadoHttpError("O CT-e precisa conter filial, série, número e chave de acesso.")
        output = self.root / cte
        output.mkdir(parents=True, exist_ok=True)
        result = {"cte": cte, "run_id": self.run_id, "submitted": False, "transport": "http"}
        try:
            number = self._opened.get(identity(row)) or await run_blocking(
                self._local_existing, row, config
            )
            checked = row.get("__novelis") or {}
            if not number and checked.get("alreadyExists"):
                number = checked.get("chamadoNumero")
            if not number and checked.get("prechecked") is not True:
                number = await self._report(row, output)
            if number:
                result.update(status="already_exists", number=str(number))
            else:
                files, title, message = await run_blocking(
                    prepare_payload, self.cwd, config, row, self.staging / cte
                )
                await emit_step(
                    self.emit,
                    self.run_id,
                    "novelis.http.form",
                    "Novelis: preparando formulário e anexos por HTTP.",
                    {"cte": cte},
                )
                prepared = await prepare(await self._client(), config, title, message, files)
                result.update(
                    status="prepared", attachments=[path.name for path in prepared.uploads.values()]
                )
                if send:
                    result = await self._send(row, prepared, output, result)
        except (httpx.HTTPError, ReportDownloadError):
            raise ChamadoHttpError(
                "A comunicação HTTP com o portal falhou. O estado de envio foi preservado para conferência."
            ) from None
        if number := result.get("number"):
            result["ticket"] = ticket(row, number)
            if result["status"] in {"confirmed", "already_exists", "duplicate"}:
                self._opened[identity(row)] = number
                try:
                    result["catalog_updated"] = await run_blocking(
                        self._remember,
                        row,
                        config,
                        number,
                        "aberto" if result["status"] == "confirmed" else "ja_existia",
                    )
                except asyncio.CancelledError:
                    record(output / "result.json", result)
                    if result["status"] == "confirmed":
                        with cancellation_scope(None):
                            await publish_result(self.emit, self.run_id, result)
                    raise
                except (CommunicationUnavailable, OSError, ValueError):
                    result["catalog_updated"] = False
        record(output / "result.json", result)
        if result["status"] == "confirmed":
            with cancellation_scope(None):
                return await publish_result(self.emit, self.run_id, result)
        return await publish_result(self.emit, self.run_id, result)
