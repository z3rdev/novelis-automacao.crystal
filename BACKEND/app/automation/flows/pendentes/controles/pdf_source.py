from app.automation.flows.flow_events import emit_step, emit_warn
from app.automation.flows.pendentes.controles.crystal_pdf import CrystalPdfRunner
from app.automation.flows.rodopar_pdf_flow.steps.rodopar_pdf import RodoparPdfFlow
from app.services.rodopar_policy import require_legacy_rodopar


def select_pdf_runner(flow):
    source = flow.legacy_config.get("PENDENTES_PDF_SOURCE", "crystal").strip().lower()
    if source == "crystal":
        return CrystalPdfRunner(flow.settings, flow.legacy_config, flow.emit).run
    if source == "rodopar":
        require_legacy_rodopar(flow.legacy_config)
        return flow._run_rodopar_pdf
    raise RuntimeError("PENDENTES_PDF_SOURCE deve ser crystal ou rodopar.")


async def run_legacy_pdf(flow, browser, rodopar_config, plan, request, run_id, config):
    """Original stage retained; never selected by a Crystal failure."""
    require_legacy_rodopar(flow.legacy_config)
    if config.get("skipRodopar"):
        await emit_step(flow.emit, run_id, "pendentes.rodopar_skip", "Rodopar PDF desabilitado na configuracao.")
        return
    rows = [item["row"] for item in plan["checked"] if item["cte"] in plan["faltandoPdf"]]
    if not rows:
        await emit_step(flow.emit, run_id, "pendentes.rodopar_skip", "Rodopar PDF: nada para fazer.")
        return
    try:
        await RodoparPdfFlow(flow.settings, flow.repository, flow.emit).run(
            browser, {**rodopar_config, "rows": rows},
            request.model_copy(update={"max_steps": None}), run_id,
        )
    except Exception:
        if config.get("stopOnError"):
            raise
        await emit_warn(
            flow.emit, run_id, "pendentes.rodopar_error",
            "Rodopar PDF falhou; demais estagios foram preservados para ajuste.",
        )
