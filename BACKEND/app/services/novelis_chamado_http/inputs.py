"""Use the same SQL, tariffs, message preferences and evidence as the app."""

from app.automation.cancellation import run_blocking
from app.automation.flows.novelis_relatorio.steps.novelis_relatorio_cte_xml import (
    NovelisRelatorioCteXmlFlow,
)
from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
from app.data.chamados_log import read_processed_ctes
from app.data.consulta_db import fetch_rows_by_documents
from app.data.cte_fields import enrich
from app.infrastructure.pending_queue import access_key, cte_number, identity
from app.services.chamados_catalog import ChamadosCatalog
from app.services.novelis_report_http import download_report
from app.services.tariffs.audit import TariffAuditService, message_fields

from . import ChamadoHttpError
from .payload import prepare_payload
from .report_lookup import existing_number, report_period


def resolve_inputs(settings, config, cte, output):
    wanted = dict(zip(("filial", "serie", "documento"), cte.split("-")))
    rows = fetch_rows_by_documents(config.consulta_db(), [wanted]).rows
    if len(rows) != 1 or cte_number(rows[0]) != cte or not access_key(rows[0]):
        raise ChamadoHttpError("O SQL não retornou um único CT-e com a identidade solicitada.")
    row = enrich(rows[0])
    row = message_fields(row, TariffAuditService(config).rows([row]).get(identity(row)))
    cfg = config.chamado_novelis()
    builder = PendentesPlanBuilder(settings.backend_root.parent, None, cache_directories=True)
    evidence = builder.resolve_evidence(
        row, config.rodopar_pdf(), config.xml_sefaz(), config.comprovante_local()
    )
    if not evidence["pdfFile"] or not evidence["xmlFile"]:
        raise ChamadoHttpError("O CT-e precisa ter PDF e XML correspondentes antes do teste.")
    if not evidence["comprovanteOk"] and not cfg.get("allowMissingComprovante"):
        raise ChamadoHttpError("A configuração exige o comprovante pendente deste CT-e.")
    cfg = {**cfg, "evidence": evidence}
    files, title, message = prepare_payload(settings.backend_root.parent, cfg, row, output)
    return row, cfg, files, title, message


async def existing_ticket(settings, config, row, output, *, fresh=False):
    cfg = config.chamado_novelis()
    hit = (
        read_processed_ctes(cfg.get("chamadosLogFile")).get(cte_number(row), {})
        if not fresh
        else {}
    )
    if number := existing_number([hit], row):
        return number
    catalog = ChamadosCatalog(settings.backend_root.parent, config)
    if catalog.repository.enabled and not fresh:
        hits = await run_blocking(catalog.opened_identities, [row])
        if number := existing_number(hits, row):
            return number
    flow = NovelisRelatorioCteXmlFlow(settings.backend_root.parent, None)
    period = report_period(row, flow._date_range(cfg))
    name = "reconciliation-report.xlsx" if fresh else "consulta-novelis.xlsx"
    report = await download_report(cfg, period, output / name)
    rows = await run_blocking(flow._parse_excel, report["file"])
    return next(
        (
            str(hit["chamadoNumero"])
            for hit in rows
            if access_key(hit) == access_key(row) and hit.get("chamadoNumero")
        ),
        "",
    )
