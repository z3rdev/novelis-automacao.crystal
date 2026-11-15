"""Execute the saved visual sequence through the existing fiscal stages."""

from datetime import datetime

from app.automation.cancellation import check_cancelled, run_blocking
from app.automation.flows.flow_events import emit_step
from app.automation.flows.novelis_relatorio.steps.novelis_relatorio_cte_xml import (
    NovelisRelatorioCteXmlFlow,
)
from app.automation.flows.pendentes.controles.opening_queue import include_opening_queue
from app.automation.flows.pendentes.controles.pdf_source import select_pdf_runner
from app.automation.flows.pendentes.steps.pendentes import PendentesFlow
from app.domain.scheduled_workflow import FINALIZERS, NODE_LABELS, NODE_STAGES
from app.infrastructure.json_store import write_json
from app.services.novelis_report_http import download_report
from app.services.tariffs.errors import TariffRefreshError

from .comparison import compare_report
from .tariffs import refresh_tariffs


class ScheduledWorkflowRunner:
    def __init__(self, settings, config, repository, emit, clock=None):
        self.flow = PendentesFlow(settings, config, repository, emit)
        self.legacy, self.emit = config, emit
        self.clock = clock or (lambda: datetime.now().astimezone())

    async def run(self, browser, request, run_id):
        self.request, self.run_id, self.browser = request, run_id, browser
        self.today = self.clock().date()
        self.root = self.flow.cwd / "captures" / "workflows" / run_id
        self.config = {
            **self.legacy.pendentes(),
            "refreshSql": True,
            "strictSql": True,
            "skipPdf": False,
            "skipXml": False,
            "skipComprovantes": False,
            "skipNovelis": False,
            "queueEligible": False,
            "outputFile": str(self.root / "plan.json"),
        }
        self.chamados = {**self.legacy.chamado_novelis(), "relatorioCteXmlTransport": "http"}
        self.pdf = self.legacy.rodopar_pdf()
        self.xml = self.legacy.xml_sefaz()
        self.proofs = self.legacy.comprovante_local()
        self.rows, self.report_rows, self.plan = [], [], None
        nodes = request.workflow.ordered_nodes()
        if request.dry_run:
            await emit_step(
                self.emit,
                run_id,
                "workflow.dry_run",
                "Prévia do fluxo personalizado.",
                {"steps": [NODE_LABELS[node.kind] for node in nodes]},
            )
            return {"dry_run": True, "errors": []}
        actions = {
            "tariffs": self.tariffs,
            "novelis_report": self.report,
            "sql": self.sql,
            "compare": self.compare,
            "files": self.files,
            "pdf": self.documents,
            "xml": self.documents,
            "proof": self.documents,
            "tickets": self.tickets,
        }
        for index, node in enumerate(nodes, 1):
            if node.kind in FINALIZERS:
                break
            check_cancelled()
            payload = {
                "node_id": node.id,
                "node_kind": node.kind,
                "stage": NODE_STAGES[node.kind],
                "node_index": index,
                "node_count": len(nodes),
                "workflow_name": request.workflow.name,
            }
            await emit_step(
                self.emit, run_id, "workflow.node.started", NODE_LABELS[node.kind], payload
            )
            try:
                check_cancelled()
                await actions[node.kind](node)
                check_cancelled()
            except Exception as exc:
                failure = payload
                message = f"Falha na etapa {NODE_LABELS[node.kind].lower()}."
                if isinstance(exc, TariffRefreshError):
                    message = str(exc)
                    failure = {**payload, "sync_stage": exc.stage, "error_code": exc.code}
                await self.emit(
                    message,
                    run_id=run_id,
                    kind="workflow.node.failed",
                    level="error",
                    payload=failure,
                )
                raise
            await emit_step(
                self.emit,
                run_id,
                "workflow.node.completed",
                f"{NODE_LABELS[node.kind]} concluído.",
                {**payload, "done": self.node_total(node), "total": self.node_total(node)},
            )
        if self.plan is None and self.rows:
            await self.ensure_plan()
        return self.plan or {"rows": self.rows, "checked": [], "errors": []}

    def node_total(self, node):
        if node.kind == "tariffs":
            return self.tariff_total
        if node.kind == "novelis_report":
            return len(self.report_rows)
        if node.kind in {"sql", "compare"}:
            return len(self.rows)
        return getattr(self, "stage_total", 0)

    async def tariffs(self, node):
        status = await refresh_tariffs(self.legacy, self.emit, self.run_id)
        self.tariff_total = status["total"]
        self.plan = None

    async def report(self, node):
        start, end = node.options.period(self.today)
        period = {"startBR": start.strftime("%d/%m/%Y"), "endBR": end.strftime("%d/%m/%Y")}
        await emit_step(
            self.emit,
            self.run_id,
            "novelis_relatorio.http_download",
            f"Relatório Novelis: consultando de {period['startBR']} até {period['endBR']}.",
            {"querySource": "novelis", "dateRange": period},
        )
        info = await download_report(self.chamados, period, self.root / f"report-{node.id}.xlsx")
        report = NovelisRelatorioCteXmlFlow(self.flow.cwd, self.emit)
        self.report_rows = await run_blocking(report._parse_excel, info["file"])
        await run_blocking(
            write_json,
            self.root / f"report-{node.id}.json",
            report._payload(info, self.report_rows),
        )
        await emit_step(
            self.emit,
            self.run_id,
            "novelis_relatorio.downloaded",
            f"Relatório Novelis: {len(self.report_rows)} registros carregados por HTTP.",
            {"querySource": "novelis", "total": len(self.report_rows)},
        )

    async def sql(self, node):
        start, end = node.options.period(self.today)
        self.config.update(
            sqlSourceJson=str(self.root / f"sql-{node.id}.json"), queueEligible=False
        )
        source = await self.flow._refresh_sql_source(
            self.config, self.legacy.consulta_db(), self.run_id, start_date=start, end_date=end
        )
        if source is None:
            raise RuntimeError("A consulta SQL do fluxo não produziu uma fonte de dados.")
        source = await include_opening_queue(self.flow.settings, source, self.request, self.emit, self.run_id,
                                            self.flow.legacy_config.consulta_db())
        self.config["sourceJson"] = str(source)
        self.request = self.request.model_copy(
            update={"consulta_data_inicio": start, "consulta_data_fim": end}
        )
        lightweight = await self.flow._refresh_plan(
            self.config,
            self.pdf,
            self.xml,
            self.proofs,
            self.request,
            self.run_id,
            check_files=False,
        )
        self.rows, self.plan = lightweight["rows"], None

    async def compare(self, node):
        self.rows, existing = await run_blocking(
            compare_report, self.flow.cwd, self.emit, self.rows, self.report_rows
        )
        source = self.root / f"novelis-filtered-{node.id}.json"
        await run_blocking(
            write_json,
            source,
            {
                "rows": self.rows,
                "queueEligible": True,
                "sourceKind": "python_pendentes_novelis_filtered",
                "total": len(self.rows),
            },
        )
        self.config.update(sourceJson=str(source), queueEligible=True)
        self.plan = None
        await emit_step(
            self.emit,
            self.run_id,
            "pendentes.novelis_relatorio",
            f"Comparação Novelis: {len(existing)} já existentes e {len(self.rows)} sem chamado.",
            {"querySource": "novelis", "total": len(self.rows), "existing": len(existing)},
        )

    async def ensure_plan(self):
        if self.plan is None:
            self.plan = await self.flow._refresh_plan(
                self.config, self.pdf, self.xml, self.proofs, self.request, self.run_id
            )
        return self.plan

    async def files(self, node):
        self.plan = None
        plan = await self.ensure_plan()
        self.stage_total = plan["total"]

    async def documents(self, node):
        plan = await self.ensure_plan()
        if node.kind == "proof":
            plan = {
                **plan,
                "faltandoComprovante": [
                    item["cte"] for item in plan["checked"] if not item["evidence"]["comprovanteOk"]
                ],
            }
        missing = {"pdf": "faltandoPdf", "xml": "faltandoXml", "proof": "faltandoComprovante"}
        changed = bool(plan[missing[node.kind]])
        self.stage_total = len(plan[missing[node.kind]])
        if node.kind == "pdf":
            await select_pdf_runner(self.flow)(
                self.browser, self.pdf, plan, self.request, self.run_id, self.config
            )
        elif node.kind == "xml":
            await self.flow._run_xml_sefaz(
                self.browser,
                self.xml,
                plan,
                self.request,
                self.run_id,
                self.config,
                self.flow._plan_file(self.config),
            )
        else:
            await self.flow._run_comprovantes(
                self.proofs, plan, self.request, self.run_id, self.config
            )
        if changed:
            self.plan = None

    async def tickets(self, node):
        plan = await self.ensure_plan()
        self.stage_total = len(plan["prontosChamado"])
        await self.flow._run_chamados(
            None,
            self.chamados,
            plan,
            self.request,
            self.run_id,
            self.config,
            self.flow._plan_file(self.config),
        )
        if plan.get("errors"):
            raise RuntimeError(
                f"Abertura de chamados finalizada com {len(plan['errors'])} pendência(s)."
            )
