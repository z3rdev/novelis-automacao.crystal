"""Refresh only missing access keys before attempting the SEFAZ download."""

from app.automation.cancellation import run_blocking
from app.automation.flows.flow_events import emit_step, emit_warn
from app.data.consulta_db import fetch_rows_by_documents
from app.infrastructure.pending_queue import access_key, cte_number


def xml_row(item, rows):
    row = next((row for row in rows if cte_number(row) == item["cte"]), {})
    key = access_key(item.get("row", {})) or access_key(row)
    row = {**row, **item.get("row", {})}
    if key:
        row["cteId"] = key
    if not cte_number(row):
        parts = item["cte"].split("-")
        row = {**row, **dict(zip(("filial", "serie", "documento"), parts))}
    return row


def missing_key_message(cte, row):
    authorization = row.get("CTEAUT")
    if authorization is None:
        authorization = (row.get("__sql") or {}).get("CTEAUT")
    detail = (
        " O Rodopar registra CTEAUT=N, sem autorização confirmada."
        if str(authorization or "").strip().upper() == "N"
        else ""
    )
    return (
        f"CT-e {cte} sem chave de acesso de 44 dígitos no Rodopar.{detail} "
        "Confira a emissão e a autorização no Rodopar antes de tentar baixar o XML."
    )


async def refresh_xml_rows(flow, items, plan, run_id):
    rows = {item["cte"]: xml_row(item, plan.get("rows", [])) for item in items}
    missing = [row for row in rows.values() if not access_key(row)]
    legacy = getattr(flow, "legacy_config", None)
    db_config = legacy.consulta_db() if legacy else {}
    if not missing or not db_config.get("enabled"):
        return rows
    await emit_step(
        flow.emit,
        run_id,
        "xml_sefaz.key_lookup",
        f"SQL Server: atualizando a chave de {len(missing)} CT-e(s) sem chave na fila.",
        {"count": len(missing)},
    )
    try:
        result = await run_blocking(fetch_rows_by_documents, db_config, missing)
    except Exception:
        await emit_warn(
            flow.emit,
            run_id,
            "xml_sefaz.key_lookup_failed",
            "SQL Server: não foi possível atualizar as chaves ausentes. Os demais XMLs serão processados.",
        )
        return rows
    fresh = {cte_number(row): row for row in result.rows}
    recovered = 0
    for cte, row in rows.items():
        if not access_key(row) and cte in fresh:
            rows[cte] = {**row, **fresh[cte]}
            recovered += bool(access_key(rows[cte]))
    await emit_step(
        flow.emit,
        run_id,
        "xml_sefaz.keys_checked",
        f"SQL Server: {recovered} chave(s) recuperada(s); {len(missing) - recovered} CT-e(s) continuam sem chave.",
        {"recovered": recovered, "missing": len(missing) - recovered},
    )
    return rows
