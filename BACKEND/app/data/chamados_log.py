import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.infrastructure.json_store import read_json, write_json


def cte_key(filial: Any, serie: Any, documento: Any) -> str:
    return f"{_part(filial)}-{_part(serie)}-{_part(documento)}"


def read_processed_ctes(log_path: Path | str | None) -> dict[str, dict[str, Any]]:
    if not log_path:
        return {}
    payload = read_json(Path(log_path), {})
    entries = payload.get("entries") if isinstance(payload, dict) else None
    return {key: value for key, value in entries.items() if isinstance(value, dict)} if isinstance(entries, dict) else {}


def mark_cte_processed(
    log_path: Path | str | None,
    filial: Any,
    serie: Any,
    documento: Any,
    status: str,
    chamado_numero: str = "",
    cte_id: str = "",
) -> None:
    if not log_path:
        return
    log_path = Path(log_path)
    key = cte_key(filial, serie, documento)
    payload = read_json(log_path, {})
    if not isinstance(payload, dict):
        payload = {}
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        entries = {}
    entries[key] = {
        "cte": key,
        "filial": str(filial or ""),
        "serie": str(serie or ""),
        "documento": str(documento or ""),
        "cteId": str(cte_id or ""),
        "status": status,
        "chamadoNumero": chamado_numero,
        "processedAt": datetime.now(timezone.utc).isoformat(),
    }
    payload["entries"] = entries
    payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
    payload["total"] = len(entries)
    write_json(log_path, payload)


def _part(value: Any) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits.lstrip("0") or digits or str(value or "").strip().upper()
