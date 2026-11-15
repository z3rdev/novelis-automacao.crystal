"""Open ready CT-es sequentially with one authenticated HTTP session."""

from app.automation.flows.flow_events import emit_step, emit_warn
from app.services.novelis_chamado_http.session import HttpChamadosSession

from .chamado_novelis import ChamadoNovelisFlow


async def run_chamados(flow, chamado_config, plan, request, run_id, config, plan_file):
    items = [item for item in plan["checked"] if item["cte"] in plan["prontosChamado"]]
    if not items:
        await emit_step(
            flow.emit, run_id, "pendentes.novelis_skip", "Chamado Novelis: nada para fazer."
        )
        return
    async with HttpChamadosSession(flow.cwd, chamado_config, flow.emit, run_id) as session:
        for index, item in enumerate(items):
            cte = item["cte"]
            await emit_step(
                flow.emit,
                run_id,
                "chamado_novelis.progress",
                f"Chamados HTTP {index + 1}/{len(items)}: {cte}.",
                {"current": index + 1, "total": len(items), "cte": cte, "transport": "http"},
            )
            try:
                await ChamadoNovelisFlow(flow.cwd, flow.emit, http_session=session).run(
                    None,
                    {
                        **chamado_config,
                        "ctes": cte,
                        "sourceJson": str(plan_file),
                        "tarifarioJson": str(plan_file),
                        "evidence": item.get("evidence", {}),
                    },
                    request.model_copy(update={"sample_cte": cte, "max_steps": None}),
                    run_id,
                )
            except Exception as exc:
                if config.get("stopOnError"):
                    raise
                plan.setdefault("errors", []).append(
                    {"stage": "novelis", "cte": cte, "message": str(exc)}
                )
                await emit_warn(
                    flow.emit,
                    run_id,
                    "pendentes.novelis_error",
                    f"Chamado Novelis falhou para {cte}: {exc}",
                    {"cte": cte},
                )
