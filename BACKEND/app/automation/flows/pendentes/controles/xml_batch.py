"""Download missing SEFAZ XMLs sequentially, with progress for the whole batch."""

from app.automation.flows.flow_events import emit_step, emit_warn
from app.automation.flows.sefaz_xml.steps.xml_sefaz import XmlSefazFlow


async def run_xml_batch(flow, browser, xml_config, plan, request, run_id, config, plan_file):
    items = [item for item in plan["checked"] if item["cte"] in plan["faltandoXml"]]
    if not items:
        await emit_step(flow.emit, run_id, "pendentes.xml_skip",
                        f"SEFAZ: os {len(plan['checked'])} CT-e(s) do plano ja possuem XML correspondente; nenhum download necessario.",
                        {"available": len(plan["checked"]), "total": 0})
        return
    errors = []
    for index, item in enumerate(items, start=1):
        cte = item["cte"]
        await emit_step(flow.emit, run_id, "xml_sefaz.progress",
                        f"Baixando XML {index} de {len(items)}: {cte}.",
                        {"cte": cte, "current": index, "total": len(items)})
        try:
            await XmlSefazFlow(flow.cwd, flow.emit).run(
                browser, {**xml_config, "ctes": cte, "sourceJson": str(plan_file)},
                request.model_copy(update={"sample_cte": cte, "max_steps": None}), run_id,
            )
        except Exception as exc:
            errors.append(f"{cte}: {exc}")
            await emit_warn(flow.emit, run_id, "xml_sefaz.error", f"XML SEFAZ falhou para {cte}: {exc}",
                            {"cte": cte, "error": str(exc)})
            if config.get("stopOnError") or "Salvamento bloqueado" in str(exc):
                raise
    if errors:
        raise RuntimeError("XML SEFAZ com pendencias: " + "; ".join(errors))
