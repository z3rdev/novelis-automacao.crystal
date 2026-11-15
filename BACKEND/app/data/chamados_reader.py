import re
from pathlib import Path
from typing import Any

from app.infrastructure.json_store import read_json, write_json


def read_chamados_payload(workspace: Path, report_path: Any = None, snapshot_path: Any = None) -> dict[str, Any]:
    source = _source_files(workspace, report_path)
    sql_payload = read_json(source["sql"], {})
    filtered_payload = read_json(source["filtered"], {})
    report_payload = read_json(source["report"], {})

    report_rows = _list_rows(report_payload.get("rows"))
    report_index = _build_report_index(report_rows)
    queue_rows = _rows_from_sql(sql_payload, filtered_payload, report_index)
    report_rows_full = _rows_from_report(report_rows)

    # The report (relatório Novelis, since 2025-01-01) is the authoritative full
    # history; the "fila" (SQL últimos 5 dias + filtrado) only covers a narrow recent
    # window. They used to be treated as alternatives — whichever had any rows won —
    # which meant a handful of fila rows silently hid the ~1000+ report rows. Now the
    # report is always the base, and fila only backfills fields it knows that the
    # report row left blank (andamento/responsável/etc.), or adds fila-only rows the
    # report doesn't have yet.
    rows = _merge_chamado_rows(report_rows_full, queue_rows)
    source_kind = "relatorio" if report_rows_full else "fila"

    rows.sort(key=lambda item: (item.get("dataSort") or "", item.get("cte") or ""), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["id"] = row.get("id") or f"chamado-{index}"

    payload = {
        "generatedAt": filtered_payload.get("generatedAt")
        or report_payload.get("generatedAt")
        or sql_payload.get("generatedAt"),
        "sourceFile": _existing_source(source),
        "sourceKind": source_kind,
        "total": len(rows),
        "queueTotal": len(queue_rows),
        "reportTotal": len(report_rows_full),
        "solucionados": sum(1 for row in rows if row.get("aberturaNovelis") == "SOLUCIONADO"),
        "pendentes": sum(1 for row in rows if row.get("aberturaNovelis") != "SOLUCIONADO"),
        "rows": rows,
    }
    if snapshot_path:
        _write_snapshot(Path(snapshot_path), payload)
    return payload


def _write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    # Best-effort: this network file lets other machines (whose local
    # captures/pendentes/*.json sources this function also reads aren't shared) fall
    # back to the last computed list when checking for duplicate chamados. A write
    # failure here (network hiccup) must never break the screen or the automation.
    try:
        write_json(path, payload)
    except Exception:
        pass


def load_chamado_rows(workspace: Path, report_path: Any, snapshot_path: Any = None) -> list[dict[str, Any]]:
    from app.services.chamados_catalog import current_catalog
    if catalog := current_catalog(workspace):
        return catalog.all_raw()
    # Local rows first so a fresh local computation is preferred; the network snapshot
    # (from whichever machine last computed it) only fills in what local sources miss.
    rows = list(read_chamados_payload(workspace, report_path).get("rows", []))
    if snapshot_path:
        snapshot_payload = read_json(Path(snapshot_path), {})
        snapshot_rows = snapshot_payload.get("rows") if isinstance(snapshot_payload, dict) else None
        if snapshot_rows:
            rows.extend(snapshot_rows)
    return rows


def find_chamado_for_cte(
    workspace: Path,
    report_path: Any,
    filial: Any,
    serie: Any,
    documento: Any,
    snapshot_path: Any = None,
    cte_id: Any = None,
) -> dict[str, Any] | None:
    rows = load_chamado_rows(workspace, report_path, snapshot_path)
    return search_chamado_rows(rows, filial, serie, documento, cte_id)


def search_chamado_rows(
    rows: list[dict[str, Any]],
    filial: Any,
    serie: Any,
    documento: Any,
    cte_id: Any = None,
) -> dict[str, Any] | None:
    target_filial = _part(filial)
    target_serie = _part(serie)
    target_doc = _part(documento)
    target_cte_id = _normalize_cte_id(cte_id)
    if not target_serie or not target_doc:
        return None
    for row in rows:
        if not row.get("chamado"):
            continue
        row_cte_id = _normalize_cte_id(row.get("cteId"))
        if target_cte_id and row_cte_id:
            # Both sides carry the actual 44-digit chave de acesso -- the
            # only identifier that's truly unambiguous. Serie+documento
            # alone is not: those numbers get reused across branches and
            # fiscal years, so an old, already-solved CT-e can share a
            # serie+documento with an unrelated, genuinely pending one
            # issued much later. Once we have both chaves, trust that
            # comparison and skip the loose fallback below entirely,
            # rather than treat a serie+documento coincidence as a match.
            if row_cte_id == target_cte_id:
                return row
            continue
        parts = str(row.get("cte") or "").split("-")
        if len(parts) < 2:
            continue
        row_filial = _part(parts[-3]) if len(parts) >= 3 else ""
        row_serie, row_doc = _part(parts[-2]), _part(parts[-1])
        if row_serie != target_serie or row_doc != target_doc:
            continue
        if target_filial and row_filial and row_filial != target_filial:
            continue
        return row
    return None


def _normalize_cte_id(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


_MERGE_BACKFILL_FIELDS = (
    "andamento",
    "responsavel",
    "origem",
    "destino",
    "vlrTotal",
    "idTarifario",
    "jda",
    "cteId",
)


def _merge_chamado_rows(
    report_rows: list[dict[str, Any]],
    queue_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in report_rows:
        key = _merge_key(row)
        if not key:
            continue
        merged[key] = row
        order.append(key)
    for row in queue_rows:
        key = _merge_key(row)
        if not key:
            continue
        if key not in merged:
            merged[key] = row
            order.append(key)
            continue
        base = merged[key]
        for field in _MERGE_BACKFILL_FIELDS:
            if not base.get(field) and row.get(field):
                base[field] = row[field]
    return [merged[key] for key in order]


def _merge_key(row: dict[str, Any]) -> str:
    # Report-sourced rows carry "serie-documento" (no filial); fila-sourced rows
    # carry "filial-serie-documento" when available. Match on serie+documento only so
    # the two shapes line up regardless of which side lacks the filial.
    parts = str(row.get("cte") or "").split("-")
    if len(parts) < 2:
        return ""
    serie, documento = _part(parts[-2]), _part(parts[-1])
    if not serie or not documento:
        return ""
    return f"{serie}|{documento}"


def _source_files(workspace: Path, report_path: Any = None) -> dict[str, Path]:
    return {
        "filtered": workspace / "captures" / "pendentes" / "novelis-filtered.json",
        "sql": workspace / "captures" / "pendentes" / "sql-ultimos-5-dias.json",
        "report": Path(report_path) if report_path else workspace / "captures" / "novelis-relatorio-cte-xml" / "relatorio_cte.json",
    }


def _existing_source(source: dict[str, Path]) -> str:
    for key in ("filtered", "sql", "report"):
        if source[key].exists():
            return str(source[key])
    return ""


def _list_rows(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _rows_from_sql(
    sql_payload: dict[str, Any],
    filtered_payload: dict[str, Any],
    report_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    seen: set[str] = set()
    for row in _list_rows(sql_payload.get("rows")):
        chamado = _report_for_row(row, report_index) or _novelis_data(row)
        normalized = _normalize_sql_row(row, chamado)
        if not normalized.get("chamado"):
            continue
        rows.append(normalized)
        seen.add(_cte_key(normalized))

    for row in _list_rows(filtered_payload.get("existingRows")):
        chamado = _novelis_data(row) or _report_for_row(row, report_index)
        normalized = _normalize_sql_row(row, chamado)
        key = _cte_key(normalized)
        if key and key not in seen and normalized.get("chamado"):
            rows.append(normalized)
            seen.add(key)
    return rows


def _filial_from_cte_id(cte_id: Any) -> str:
    # The report itself never carries a filial field, but the CT-e chave de
    # acesso (44 digits) does: digits[6:20] is the emitting CNPJ, and a
    # Brazilian CNPJ's own digits 8-11 (the "ordem" segment, matriz=0001,
    # branches 0002+) are the filial number directly -- no lookup table
    # needed, same derivation `_row_from_cte` already uses elsewhere for
    # manually-entered CTE keys (plan.py, manual_input.py).
    digits = re.sub(r"\D", "", str(cte_id or ""))
    if len(digits) != 44:
        return ""
    cnpj = digits[6:20]
    return _part(cnpj[8:12])


def _rows_from_report(report_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in report_rows:
        chamado = _text(row.get("chamadoNumero"))
        if not chamado:
            continue
        serie = _text(row.get("serie"))
        documento = _text(row.get("documento") or row.get("nCT"))
        filial = _filial_from_cte_id(row.get("cteId"))
        rows.append(
            {
                "cte": "-".join(part for part in [filial, serie, documento] if part),
                "data": _text(row.get("abertoEm")),
                "dataSort": _date_sort(row.get("abertoEm")),
                "abertoEm": _date_sort(row.get("abertoEm")),
                "vlrTotal": None,
                "aberturaNovelis": "SOLUCIONADO",
                "idTarifario": "",
                "chamado": chamado,
                "jda": "",
                "andamento": _text(row.get("andamento")),
                "responsavel": _text(row.get("atualResponsavel")),
                "origem": "",
                "destino": "",
                "cteId": _text(row.get("cteId")),
            }
        )
    return rows


def _normalize_sql_row(row: dict[str, Any], chamado_data: dict[str, Any]) -> dict[str, Any]:
    chamado = _text(
        chamado_data.get("chamadoNumero")
        or chamado_data.get("chamadoId")
        or row.get("chamadoNumero")
        or row.get("chamadoId")
        or row.get("CHAMADO_ID")
    )
    cte = _cte_label(row)
    data = _text(row.get("data") or row.get("DATA"))
    return {
        "cte": cte,
        "data": data,
        "dataSort": _date_sort(data),
        "abertoEm": _date_sort(chamado_data.get("abertoEm")),
        "vlrTotal": _number(row.get("VLR_TOTAL") or row.get("vlrTotal") or row.get("valorTotal")),
        "aberturaNovelis": "SOLUCIONADO" if chamado else "PENDENTE",
        "idTarifario": _text(row.get("ID_TARIFARIO") or row.get("idTarifario") or row.get("tarifarioId")),
        "chamado": chamado,
        "jda": _text(row.get("JDA") or row.get("jda") or row.get("ID_JDA")),
        "andamento": _text(chamado_data.get("andamento")),
        "responsavel": _text(chamado_data.get("atualResponsavel")),
        "origem": _text(row.get("origem") or row.get("LOCCOL") or row.get("REM_CIDADE")),
        "destino": _text(row.get("destino") or row.get("LOCENT") or row.get("DES_CIDADE")),
        "cteId": _text(row.get("cteId") or row.get("CTE_ID")),
    }


def _build_report_index(report_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in report_rows:
        digits = _digits(row.get("cteIdDigits") or row.get("cteId") or row.get("id"))
        if digits:
            index[f"cte:{digits}"] = row
        serie = _text(row.get("serie"))
        documento = _text(row.get("documento") or row.get("nCT"))
        if serie and documento:
            index[f"serie_doc:{serie}|{documento}"] = row
    return index


def _report_for_row(row: dict[str, Any], report_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    digits = _digits(row.get("cteId") or row.get("CTE_ID"))
    if digits and f"cte:{digits}" in report_index:
        return report_index[f"cte:{digits}"]
    serie = _text(row.get("serie") or row.get("SERIE"))
    documento = _text(row.get("documento") or row.get("DOCUMENTO"))
    return report_index.get(f"serie_doc:{serie}|{documento}", {})


def _novelis_data(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("__novelis")
    return value if isinstance(value, dict) else {}


def _cte_label(row: dict[str, Any]) -> str:
    cte = _text(row.get("cte") or row.get("numeroCte"))
    if cte:
        return cte
    filial = _text(row.get("filial") or row.get("FILIAL"))
    serie = _text(row.get("serie") or row.get("SERIE"))
    documento = _text(row.get("documento") or row.get("DOCUMENTO"))
    return "-".join(part for part in [filial, serie, documento] if part)


def _cte_key(row: dict[str, Any]) -> str:
    return _text(row.get("cte") or row.get("cteId"))


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _digits(value: Any) -> str:
    return re.sub(r"\D+", "", _text(value))


def _part(value: Any) -> str:
    digits = _digits(value)
    return digits.lstrip("0") or digits or _text(value).upper()


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _text(value).replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _date_sort(value: Any) -> str:
    text = _text(value)
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text
    match = re.match(r"(\d{2})/(\d{2})/(\d{4})(.*)", text)
    if match:
        day, month, year, suffix = match.groups()
        return f"{year}-{month}-{day}{suffix}"
    return text
