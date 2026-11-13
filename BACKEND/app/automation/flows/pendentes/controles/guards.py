import re
import unicodedata
from pathlib import Path
from typing import Any


def should_block_unfiltered_execution(
    config: dict[str, Any],
    plan: dict[str, Any],
    filtered_source: Path | None,
    sample_cte: str | None,
    sample_filial: str | None,
    sample_documento: str | None,
) -> bool:
    if filtered_source or not config.get("requireNovelisFilterBeforeExecution"):
        return False
    if sample_cte or sample_filial or sample_documento:
        return False
    if _is_known_pending_source(plan):
        return False
    return bool(plan.get("checked"))


def _is_known_pending_source(plan: dict[str, Any]) -> bool:
    source = str(plan.get("sourceFile") or "").lower().replace("\\", "/")
    if any(token in source for token in ("novelis-filtered", "latest-enriched", "pendentes-comandos")):
        return True
    rows = plan.get("rows") if isinstance(plan.get("rows"), list) else []
    if not rows:
        return True
    statuses = [_status_token(row.get("status") or row.get("STATUS")) for row in rows]
    if any(status == "SQL_ULTIMOS_5_DIAS" for status in statuses):
        return False
    return all((not status or "AGUARDANDO" in status) for status in statuses)


def _status_token(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")
