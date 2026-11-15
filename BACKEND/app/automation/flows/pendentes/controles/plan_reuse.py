"""Retain verified evidence when the final report only removes opened CT-es."""

from datetime import UTC, datetime

from app.infrastructure.pending_queue import cte_number, identity
from app.domain.cte_authorization import authorization_status


def rows_plan(normalized_rows, checked, source_file, sheet_name, total_consultados):
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "sourceFile": source_file,
        "sheetName": sheet_name,
        "consultados": total_consultados,
        "filtradosFora": total_consultados - len(normalized_rows),
        "total": len(checked),
        "rows": [item["row"] for item in checked],
        "checked": checked,
        "faltandoPdf": [],
        "faltandoXml": [],
        "faltandoComprovante": [],
        "prontosChamado": [],
        "prontosComprovante": [],
    }


def filtered_plan(previous, payload, source):
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return None
    rows = [row for row in rows if authorization_status(row) != "N"]
    checked = {identity(item["row"]): item for item in previous["checked"]}
    if any(identity(row) not in checked for row in rows):
        return None
    items = [{**checked[identity(row)], "row": {**checked[identity(row)]["row"], **row}} for row in rows]
    keep = {cte_number(item["row"]) for item in items}
    result = {**previous, "checked": items, "rows": [item["row"] for item in items],
              "total": len(items), "sourceFile": source,
              "generatedAt": payload.get("generatedAt") or previous.get("generatedAt")}
    for field in ("faltandoPdf", "faltandoXml", "faltandoComprovante", "prontosComprovante", "prontosChamado"):
        result[field] = [cte for cte in previous[field] if cte in keep]
    return result
