"""Download missing SEFAZ XMLs sequentially, with progress for the whole batch."""

from app.automation.flows.flow_events import emit_step, emit_warn
from app.automation.flows.sefaz_xml.steps.xml_sefaz import XmlSefazFlow
from app.automation.flows.pendentes.controles.xml_keys import missing_key_message, refresh_xml_rows
from app.infrastructure.pending_queue import access_key


async def run_xml_batch(flow, browser, xml_config, plan, request, run_id, config, plan_file):
    items = [item for item in plan["checked"] if item["cte"] in plan["faltandoXml"]]
    if not items:
        await emit_step(flow.emit, run_id, "pendentes.xml_skip",
                        f"SEFAZ: os {len(plan['checked'])} CT-e(s) do plano ja possuem XML correspondente; nenhum download necessario.",
                        {"available": len(plan["checked"]), "total": 0})
        return
    rows = await refresh_xml_rows(flow, items, plan, run_id)
    errors, failed_ctes, succeeded = [], [], 0
    for index, item in enumerate(items, start=1):
        cte = item["cte"]
        await emit_step(flow.emit, run_id, "xml_sefaz.progress",
                        f"Baixando XML {index} de {len(items)}: {cte}.",
                        {"cte": cte, "current": index, "total": len(items), "done": succeeded})
        try:
            if not access_key(rows[cte]):
                raise RuntimeError(missing_key_message(cte, rows[cte]))
            await XmlSefazFlow(flow.cwd, flow.emit).run(
                browser, {**xml_config, "ctes": cte, "targetRow": rows[cte], "sourceJson": str(plan_file)},
                request.model_copy(update={"sample_cte": cte, "max_steps": None}), run_id,
            )
            succeeded += 1
        except Exception as exc:
            errors.append(f"{cte}: {exc}")
            failed_ctes.append(cte)
            await emit_warn(flow.emit, run_id, "xml_sefaz.error", f"XML SEFAZ falhou para {cte}: {exc}",
                            {"cte": cte, "error": str(exc), "total": len(items), "done": succeeded})
            if config.get("stopOnError") or "Salvamento bloqueado" in str(exc):
                raise
    if errors:
        await emit_warn(flow.emit, run_id, "xml_sefaz.batch_failed",
                        f"XML SEFAZ: {succeeded} baixado(s), {len(errors)} com falha.",
                        {"total": len(items), "done": succeeded, "failed": len(errors), "failedCtes": failed_ctes})
        raise RuntimeError("XML SEFAZ com pendencias: " + "; ".join(errors))
    await emit_step(flow.emit, run_id, "xml_sefaz.batch_completed",
                    f"XML SEFAZ: {succeeded} baixado(s), sem pendências.",
                    {"total": len(items), "done": succeeded, "failed": 0})
