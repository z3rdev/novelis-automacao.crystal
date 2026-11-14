from pathlib import Path
from typing import Any

from app.automation.cancellation import run_blocking
from app.automation.flows.comprovantes_locais.steps.comprovante_local import ComprovanteLocalFlow
from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.automation.flows.novelis_chamados.steps.chamado_novelis import ChamadoNovelisFlow
from app.automation.flows.novelis_relatorio.steps.novelis_relatorio_cte_xml import (
    NovelisRelatorioCteXmlFlow,
)
from app.automation.flows.pendentes.controles.events import (
    emit_completed_summary,
    emit_plan_summary,
)
from app.automation.flows.pendentes.controles.execution_scope import scoped_config
from app.automation.flows.pendentes.controles.guards import should_block_unfiltered_execution
from app.automation.flows.pendentes.controles.manual_input import ManualInputResolver
from app.automation.flows.pendentes.controles.pdf_source import run_legacy_pdf, select_pdf_runner
from app.automation.flows.pendentes.controles.pdf_xml_parallel import PdfXmlParallelRunner
from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
from app.automation.flows.pendentes.controles.xml_batch import run_xml_batch
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.data.consulta_db import fetch_last_5_days_rows
from app.domain.models import RunStartRequest
from app.infrastructure.json_store import write_json
from app.services.browser_driver import BrowserDriver
from app.services.step_repository import StepRepository


class PendentesFlow:
    def __init__(
        self,
        settings: Settings,
        legacy_config: LegacyConfig,
        repository: StepRepository,
        emit: Emit,
    ) -> None:
        self.settings = settings
        self.legacy_config = legacy_config
        self.repository = repository
        self.emit = emit
        self.cwd = settings.backend_root.parent

    async def run(
        self,
        browser: BrowserDriver | None,
        request: RunStartRequest,
        run_id: str,
    ) -> dict[str, Any]:
        config = scoped_config(self.legacy_config.pendentes(), request)
        pdf_runner = select_pdf_runner(self) if not config.get("skipPdf") else None
        rodopar_config = self.legacy_config.rodopar_pdf()
        if request.rodopar_replay_overlay_enabled is not None:
            rodopar_config = {
                **rodopar_config,
                "replayOverlayEnabled": request.rodopar_replay_overlay_enabled,
            }
        xml_config = self.legacy_config.xml_sefaz()
        comprovante_config = self.legacy_config.comprovante_local()
        chamado_config = self.legacy_config.chamado_novelis()
        config = await ManualInputResolver(self.cwd, self.emit).apply(
            config,
            request,
            run_id,
            self.legacy_config.consulta_db(),
        )
        if request.pendentes_sql_days_back is not None and not (
            request.manual_ctes or request.manual_spreadsheet or request.sample_cte or request.sample_documento
        ):
            config = {**config, "refreshSql": True, "strictSql": True}
        sql_source = await self._refresh_sql_source(
            config,
            self.legacy_config.consulta_db(),
            run_id,
            request.pendentes_sql_days_back,
        )
        if sql_source:
            config = {**config, "sourceJson": str(sql_source)}
        plan_file = self._plan_file(config)

        plan = await self._refresh_plan(
            config,
            rodopar_config,
            xml_config,
            comprovante_config,
            request,
            run_id,
        )
        filtered_source = await self._refresh_novelis_relatorio(
            browser,
            config,
            chamado_config,
            plan,
            request,
            run_id,
        )
        if filtered_source:
            config = {**config, "sourceJson": str(filtered_source)}
            plan = await self._refresh_plan(
                config,
                rodopar_config,
                xml_config,
                comprovante_config,
                request,
                run_id,
                "Depois da consulta Novelis",
            )

        if request.flow.strip().lower() in {"consulta-pendentes", "consulta"}:
            await emit_completed_summary(self.emit, run_id, plan_file, plan)
            return plan

        if request.dry_run:
            await emit_step(
                self.emit,
                run_id,
                "pendentes.dry_run",
                "Iniciar automação simulado; nenhum fluxo foi executado.",
                {
                    "planFile": str(plan_file),
                    "faltandoPdf": plan["faltandoPdf"],
                    "faltandoXml": plan["faltandoXml"],
                    "faltandoComprovante": plan["faltandoComprovante"],
                    "prontosChamado": plan["prontosChamado"],
                },
            )
            return plan

        if should_block_unfiltered_execution(
            config,
            plan,
            filtered_source,
            request.sample_cte,
            request.sample_filial,
            request.sample_documento,
        ):
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.unfiltered_blocked",
                (
                    "Filtro Novelis não confirmou a fila de aguardando aprovação; "
                    f"execução bloqueada para não processar {plan.get('consultados', plan['total'])} consultado(s) "
                    f"como pendente(s). PDF={len(plan['faltandoPdf'])}, XML={len(plan['faltandoXml'])}."
                ),
                {
                    "sourceFile": plan.get("sourceFile") or "",
                    "consultados": plan.get("consultados", plan["total"]),
                    "totalPlano": plan["total"],
                    "faltandoPdf": plan["faltandoPdf"],
                    "faltandoXml": plan["faltandoXml"],
                },
            )
            raise RuntimeError(
                "Execução bloqueada: filtro Novelis não confirmou a fila de "
                "aguardando aprovação."
            )

        plan = await PdfXmlParallelRunner(
            self.settings,
            self.emit,
            pdf_runner,
            self._run_xml_sefaz,
            self._refresh_plan,
        ).run(browser, rodopar_config, xml_config, comprovante_config, plan, request, run_id, config, plan_file)

        if not config.get("skipComprovantes"):
            await self._run_comprovantes(comprovante_config, plan, request, run_id, config)
            plan = await self._refresh_plan(
                config,
                rodopar_config,
                xml_config,
                comprovante_config,
                request,
                run_id,
                "Depois dos comprovantes",
            )

        if not config.get("skipNovelis"):
            await self._run_chamados(browser, chamado_config, plan, request, run_id, config, plan_file)
            final_source = await self._refresh_novelis_relatorio_final(browser, config, chamado_config, plan, request, run_id)
            if final_source:
                errors = plan.get("errors") or []
                config = {**config, "sourceJson": str(final_source)}
                plan = await self._refresh_plan(config, rodopar_config, xml_config, comprovante_config, request, run_id, "Depois do relatório final Novelis")
                if errors:
                    plan["errors"] = errors

        await emit_completed_summary(self.emit, run_id, plan_file, plan)
        return plan

    async def _refresh_sql_source(
        self,
        config: dict[str, Any],
        db_config: dict[str, Any],
        run_id: str,
        days_back: int | None = None,
    ) -> Path | None:
        if not config.get("refreshSql") or not db_config.get("enabled"):
            if config.get("strictSql"):
                raise RuntimeError("Consulta por período exige a conexão SQL habilitada. Verifique CONSULTA_DB_ENABLED e a configuração do banco neste computador.")
            await emit_step(
                self.emit, run_id, "pendentes.sql_disabled",
                "Consulta SQL desabilitada na configuracao; verificando fonte local.",
                {"refreshSql": bool(config.get("refreshSql")), "enabled": bool(db_config.get("enabled"))},
            )
            return None

        days = max(0, int(days_back if days_back is not None else 5))
        period = "do dia atual" if days == 0 else f"dos ultimos {days} dias, incluindo hoje"
        await emit_step(
            self.emit,
            run_id,
            "pendentes.sql_refresh",
            f"Consultando SQL {period} para montar pendentes.",
        )
        try:
            result = await run_blocking(fetch_last_5_days_rows, db_config, days)
        except Exception as exc:
            if config.get("strictSql"):
                raise
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.sql_error",
                f"Consulta SQL de pendentes falhou; seguindo com fonte local: {exc}",
            )
            return None

        output_file = self._resolve(config.get("sqlSourceJson") or "captures/pendentes/sql-ultimos-5-dias.json")
        write_json(
            output_file,
            {
                "generatedAt": result.source.get("generatedAt"),
                "sourceKind": "python_sql_ultimos_5_dias",
                "sourceFile": result.source_file,
                "source": result.source,
                "total": len(result.rows),
                "rows": result.rows,
            },
        )
        await emit_step(
            self.emit,
            run_id,
            "pendentes.sql_loaded",
            f"SQL {period} carregado: {len(result.rows)} CTE(s).",
            {"sourceJson": str(output_file), "total": len(result.rows)},
        )
        return output_file

    async def _refresh_novelis_relatorio(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        chamado_config: dict[str, Any],
        plan: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> Path | None:
        if config.get("skipNovelis") or not config.get("refreshNovelisRelatorio"):
            return None

        rows = plan.get("rows") if isinstance(plan.get("rows"), list) else []
        if not rows:
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.novelis_relatorio_empty_plan",
                "Plano de pendentes vazio; baixando Excel Novelis mesmo assim para atualizar a consulta.",
            )

        try:
            relatorio = await NovelisRelatorioCteXmlFlow(self.cwd, self.emit).run(
                browser,
                chamado_config,
                rows,
                run_id,
            )
        except Exception as exc:
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.novelis_relatorio_error",
                f"Consulta Novelis/Excel falhou; execução bloqueada para não usar fila original: {exc}",
            )
            raise RuntimeError(
                "Execução bloqueada: Consulta Novelis/Excel falhou e a fila original "
                "não pode ser usada como pendente."
            ) from exc

        if relatorio.get("skipped"):
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.novelis_relatorio_skipped",
                f"Consulta Novelis/Excel pulada: {relatorio.get('error') or 'sem motivo informado'}.",
            )
            return None

        filtered_file = self._resolve(config.get("filteredSourceJson") or "captures/pendentes/novelis-filtered.json")
        write_json(
            filtered_file,
            {
                "generatedAt": relatorio.get("payload", {}).get("generatedAt"),
                "sourceKind": "python_pendentes_novelis_filtered",
                "sourceFile": plan.get("sourceFile") or "",
                "relatorioExcelFile": relatorio.get("excelFile") or "",
                "relatorioJsonFile": relatorio.get("jsonFile") or "",
                "dateRange": relatorio.get("dateRange"),
                "totalOriginal": len(rows),
                "totalExistingNovelis": len(relatorio.get("existingRows") or []),
                "totalPending": len(relatorio.get("rows") or []),
                "existingRows": relatorio.get("existingRows") or [],
                "rows": relatorio.get("rows") or [],
            },
        )
        await emit_step(
            self.emit,
            run_id,
            "pendentes.novelis_relatorio",
            (
                f"Consulta Novelis aplicada: {len(relatorio.get('existingRows') or [])} já existente(s), "
                f"{len(relatorio.get('rows') or [])} segue(m) pendente(s)."
            ),
            {"filteredSourceJson": str(filtered_file), "excelFile": relatorio.get("excelFile") or ""},
        )
        return filtered_file

    async def _refresh_novelis_relatorio_final(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        chamado_config: dict[str, Any],
        plan: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> Path | None:
        if not config.get("refreshNovelisRelatorioAfterChamados", True):
            return None
        refreshed = await self._refresh_novelis_relatorio(browser, config, chamado_config, plan, request, run_id)
        await emit_step(
            self.emit,
            run_id,
            "pendentes.novelis_relatorio_final",
            "Relatório Novelis atualizado após abertura dos chamados." if refreshed else "Relatório Novelis final não foi atualizado.",
            {"filteredSourceJson": str(refreshed or "")},
        )
        return refreshed

    async def _refresh_plan(
        self,
        config: dict[str, Any],
        rodopar_config: dict[str, Any],
        xml_config: dict[str, Any],
        comprovante_config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        label: str = "Plano de pendentes",
    ) -> dict[str, Any]:
        plan = await PendentesPlanBuilder(self.cwd, self.emit).build(
            config,
            rodopar_config,
            xml_config,
            comprovante_config,
            request,
            run_id,
            self.legacy_config.chamado_novelis(),
        )
        self._write_plan(config, plan)
        await emit_plan_summary(self.emit, plan, run_id, label)
        return plan

    async def _run_rodopar_pdf(
        self,
        browser: BrowserDriver | None,
        rodopar_config: dict[str, Any],
        plan: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        config: dict[str, Any],
    ) -> None:
        await run_legacy_pdf(self, browser, rodopar_config, plan, request, run_id, config)

    async def _run_xml_sefaz(
        self,
        browser: BrowserDriver | None,
        xml_config: dict[str, Any],
        plan: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        config: dict[str, Any],
        plan_file: Path,
    ) -> None:
        await run_xml_batch(self, browser, xml_config, plan, request, run_id, config, plan_file)

    async def _run_comprovantes(
        self,
        comprovante_config: dict[str, Any],
        plan: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        config: dict[str, Any],
    ) -> None:
        items = [item for item in plan["checked"] if item["cte"] in plan["faltandoComprovante"]]
        if not items:
            await emit_step(
                self.emit,
                run_id,
                "pendentes.comprovantes_skip",
                "Comprovantes locais: nada para fazer.",
            )
            return
        try:
            await ComprovanteLocalFlow(self.cwd, self.emit).run(
                {**comprovante_config, "rows": [item["row"] for item in items]},
                request.model_copy(
                    update={"sample_cte": "", "sample_filial": "", "sample_documento": "", "max_steps": None}
                ),
                run_id,
            )
        except Exception as exc:
            if config.get("stopOnError"):
                raise
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.comprovantes_error",
                f"Comprovantes locais falharam: {exc}",
            )

    async def _run_chamados(
        self,
        browser: BrowserDriver | None,
        chamado_config: dict[str, Any],
        plan: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        config: dict[str, Any],
        plan_file: Path,
    ) -> None:
        items = [item for item in plan["checked"] if item["cte"] in plan["prontosChamado"]]
        if not items:
            await emit_step(self.emit, run_id, "pendentes.novelis_skip", "Chamado Novelis: nada para fazer.")
            return
        for index, item in enumerate(items):
            cte = item["cte"]
            await emit_step(
                self.emit,
                run_id,
                "chamado_novelis.progress",
                f"Chamados {index + 1}/{len(items)}: {cte}.",
                {"current": index + 1, "total": len(items), "cte": cte},
            )
            try:
                await ChamadoNovelisFlow(self.cwd, self.emit).run(
                    browser,
                    {
                        **chamado_config,
                        "ctes": cte,
                        "sourceJson": str(plan_file),
                        "tarifarioJson": str(plan_file), "evidence": item.get("evidence", {}),
                    },
                    request.model_copy(update={"sample_cte": cte, "max_steps": None}),
                    run_id,
                )
            except Exception as exc:
                if config.get("stopOnError"):
                    raise
                await emit_warn(
                    self.emit,
                    run_id,
                    "pendentes.novelis_error",
                    f"Chamado Novelis falhou para {cte}: {exc}",
                    plan.setdefault("errors", []).append({"stage": "novelis", "cte": cte, "message": str(exc)}) or {"cte": cte},
                )

    def _write_plan(self, config: dict[str, Any], plan: dict[str, Any]) -> Path:
        path = self._plan_file(config)
        write_json(path, plan)
        return path

    def _plan_file(self, config: dict[str, Any]) -> Path:
        return self._resolve(config.get("outputFile") or "captures/pendentes/latest-python.json")

    def _resolve(self, value: str) -> Path:
        path = Path(str(value or ""))
        return path if path.is_absolute() else self.cwd / path
