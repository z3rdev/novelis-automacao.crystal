"""Single HTTP test shared by the app workflow and the command-line entry point."""

import asyncio
import json
import re

from app.automation.cancellation import check_cancelled, run_blocking
from app.infrastructure.chamados_postgres import CommunicationUnavailable
from app.services.chamados_catalog import ChamadosCatalog
from app.services.execution_reports.models import ticket
from app.services.novelis_report_http import authenticated

from . import ChamadoHttpError, load_form, prepare, submit_once, verify_ticket
from .inputs import existing_ticket, resolve_inputs
from .outcomes import record


async def probe(config, output):
    async with authenticated(config.novelis()) as client:
        form, dynamic, _, _ = await load_form(client, config.novelis())
        result = {
            "status": "form_verified",
            "submitted": False,
            "form_http": 200,
            "dynamic_fields_http": 200,
            "upload_fields": list(dynamic.files),
            "session_identifier_present": bool(form.fields.get("unique_number")),
        }
        record(output / "result.json", result)
        return result


async def run_ticket_test(settings, config, cte, output, *, send=False, notify=None):
    if not re.fullmatch(r"[1-9]\d*-\d+-[1-9]\d*", cte):
        raise ChamadoHttpError("Informe um CT-e no formato filial-série-número.")

    async def progress(stage, message, **payload):
        check_cancelled()
        if notify:
            await notify(stage, message, {"cte": cte, "transport": "http", **payload})

    await progress(
        "consulta.sql", "Banco de dados: consultando o CT-e para o teste HTTP.", querySource="sql"
    )
    row, cfg, files, title, message = await run_blocking(
        resolve_inputs, settings, config, cte, output
    )
    base = {
        "cte": cte,
        "submitted": False,
        "tariff_status": (row.get("tariffAudit") or {}).get("status"),
    }
    await progress(
        "consulta.novelis",
        "Relatório Novelis: conferindo se o CT-e já possui chamado.",
        querySource="novelis",
    )
    if number := await existing_ticket(settings, config, row, output):
        result = {
            **base,
            "status": "already_exists",
            "number": number,
            "ticket": ticket(row, number),
        }
        record(output / "result.json", result)
        return result
    async with authenticated(cfg) as client:
        await progress(
            "novelis.http.form", "Chamado HTTP: preparando formulário e anexos.", current=1, total=1
        )
        prepared = await prepare(client, cfg, title, message, files)
        result = {
            **base,
            "status": "prepared",
            "attachments": [path.name for path in prepared.uploads.values()],
        }
        record(output / "result.json", result)
        if not send:
            return result
        journal = output.parent / f"submission-{cte}.json"
        await progress("novelis.http.submit", "Chamado HTTP: enviando PDF, XML e ZIP.")
        try:
            with journal.open("x", encoding="utf-8") as stream:
                json.dump({**base, "status": "submitting", "output": str(output)}, stream)
        except FileExistsError:
            raise ChamadoHttpError(
                "Este CT-e já teve um envio HTTP de teste. Confira o resultado registrado antes de repetir."
            ) from None
        try:
            result = {**base, **await submit_once(client, prepared, cte)}
            if result["status"] == "indeterminate":
                record(output / "result.json", result)
                record(journal, result)
                await progress(
                    "novelis.http.reconcile",
                    "Relatório Novelis: conferindo o resultado do envio HTTP.",
                    querySource="novelis",
                )
                if number := await existing_ticket(settings, config, row, output, fresh=True):
                    result = await verify_ticket(
                        client,
                        number,
                        cte,
                        prepared.uploads,
                        {**result, "confirmation_source": "portal_report"},
                    )
        except asyncio.CancelledError:
            result = {**base, "status": "indeterminate", "submitted": True, "cancelled": True}
            record(output / "result.json", result)
            record(journal, result)
            raise
        if result.get("number"):
            result["ticket"] = ticket(row, result["number"])
        record(output / "result.json", result)
        record(journal, result)
        if result["status"] == "confirmed":
            try:
                catalog = ChamadosCatalog(settings.backend_root.parent, config)
                result["catalog_updated"] = catalog.repository.enabled
                if catalog.repository.enabled:
                    await run_blocking(catalog.record_processed, row, "aberto", result["number"])
            except (CommunicationUnavailable, OSError, ValueError):
                result["catalog_updated"] = False
            record(output / "result.json", result)
        return result
