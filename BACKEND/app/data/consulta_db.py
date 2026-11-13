import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.automation.cancellation import cancellable_cursor, check_cancelled

MAX_MANUAL_LOOKUP_ERRORS = 20


SQL_LAST_N_DAYS = """
SELECT
  R.FILIAL,
  R.SERIE,
  R.DOCUMENTO,
  R.DATA,
  R.VLR_TOTAL,
  C.VLRTAR AS VLR_TAR,
  C.OUTROS,
  C.FREVAL,
  C.NMGNRE,
  C.CTE_ID,
  C.LOCCOL,
  C.LOCENT,
  C.OBSCON,
  C.ESTCOL,
  C.ESTDES,
  R.VLR_FRETE_PESO,
  R.REM_CIDADE,
  R.DES_CIDADE,
  R.VEI_CODIGO,
  R.PEDIDO,
  R.OBSERVACAO
FROM VW_RECEBER_DELLMAR AS R
  OUTER APPLY (
    SELECT TOP (1)
      RC.VLRTAR,
      RC.OUTROS,
      RC.FREVAL,
      RC.NMGNRE,
      RC.CTE_ID,
      RC.LOCCOL,
      RC.LOCENT,
      RC.OBSCON,
      RC.ESTCOL,
      RC.ESTDES
    FROM RODCON AS RC
    WHERE RC.CODCON = R.DOCUMENTO
      AND RC.CODFIL = R.FILIAL
      AND R.TIPO = 'CTE'
  ) AS C
WHERE
  CAST(R.DATA AS DATE) BETWEEN DATEADD(DAY, ?, CAST(GETDATE() AS DATE))
    AND DATEADD(DAY, -1, CAST(GETDATE() AS DATE))
  AND (? IS NULL OR R.PAG_GRUPO_CLIENTE_COD = ?)
  AND R.TIPO = 'CTE'
ORDER BY R.DATA, R.DOCUMENTO;
"""

SQL_BY_DOCUMENT = """
SELECT TOP (1)
  R.FILIAL,
  R.SERIE,
  R.DOCUMENTO,
  R.DATA,
  R.VLR_TOTAL,
  C.VLRTAR AS VLR_TAR,
  C.OUTROS,
  C.FREVAL,
  C.NMGNRE,
  C.CTE_ID,
  C.LOCCOL,
  C.LOCENT,
  C.OBSCON,
  C.ESTCOL,
  C.ESTDES,
  R.VLR_FRETE_PESO,
  R.REM_CIDADE,
  R.DES_CIDADE,
  R.VEI_CODIGO,
  R.PEDIDO,
  R.OBSERVACAO
FROM VW_RECEBER_DELLMAR AS R
  OUTER APPLY (
    SELECT TOP (1)
      RC.VLRTAR,
      RC.OUTROS,
      RC.FREVAL,
      RC.NMGNRE,
      RC.CTE_ID,
      RC.LOCCOL,
      RC.LOCENT,
      RC.OBSCON,
      RC.ESTCOL,
      RC.ESTDES
    FROM RODCON AS RC
    WHERE RC.CODCON = R.DOCUMENTO
      AND RC.CODFIL = R.FILIAL
      AND R.TIPO = 'CTE'
  ) AS C
WHERE R.FILIAL = ?
  AND R.DOCUMENTO = ?
  AND (? IS NULL OR R.SERIE = ?)
  AND R.TIPO = 'CTE'
  AND (? IS NULL OR R.PAG_GRUPO_CLIENTE_COD = ?)
ORDER BY R.DATA DESC, R.DOCUMENTO DESC;
"""


@dataclass(frozen=True)
class SqlConsultaResult:
    rows: list[dict[str, Any]]
    source_file: str
    source: dict[str, Any]


def fetch_last_5_days_rows(config: dict[str, Any], days: int = 5) -> SqlConsultaResult:
    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError("Instale pyodbc no backend para consultar pendentes SQL.") from exc

    server = str(config.get("server") or "").strip()
    user = str(config.get("user") or "").strip()
    password = str(config.get("pass") or "").strip()
    database = str(config.get("database") or "").strip()
    if not server or not user or not password:
        raise RuntimeError("Configure CONSULTA_DB_SERVER, CONSULTA_DB_USER e CONSULTA_DB_PASS.")

    days_back = max(1, int(days or 5))
    connection_string = _connection_string(config, server, user, password, database)
    for attempt in range(2):
        check_cancelled()
        try:
            return _fetch_last_days(pyodbc, connection_string, config, days_back)
        except Exception as exc:
            if attempt or not _should_retry_sql(exc):
                raise


def _fetch_last_days(
    pyodbc: Any, connection_string: str, config: dict[str, Any], days_back: int,
) -> SqlConsultaResult:
    # A killed SQL session cannot be reused. Each bounded retry owns a connection.
    connection = pyodbc.connect(
        connection_string,
        timeout=max(1, int(config.get("connectionTimeoutMs") or 15_000) // 1000),
    )
    try:
        cursor = connection.cursor()
        connection.timeout = max(1, int(config.get("requestTimeoutMs") or 20_000) // 1000)
        group = _optional_int(config.get("pagGrupoClienteCod"))
        with cancellable_cursor(cursor):
            cursor.execute(SQL_LAST_N_DAYS, -days_back, group, group)
            columns = [column[0] for column in cursor.description]
            raw_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return SqlConsultaResult(
            rows=_dedupe_rows(raw_rows),
            source_file=f"SQL_ULTIMOS_{days_back}_DIAS",
            source=_source_meta(),
        )
    finally:
        connection.close()


def fetch_rows_by_documents(config: dict[str, Any], rows: list[dict[str, Any]]) -> SqlConsultaResult:
    wanted = _wanted_documents(rows)
    if not wanted:
        return SqlConsultaResult(rows=[], source_file="SQL_CONSULTA_MANUAL", source=_source_meta())

    try:
        import pyodbc
    except ImportError as exc:
        raise RuntimeError("Instale pyodbc no backend para consultar CTE_ID no SQL.") from exc

    server = str(config.get("server") or "").strip()
    user = str(config.get("user") or "").strip()
    password = str(config.get("pass") or "").strip()
    database = str(config.get("database") or "").strip()
    if not server or not user or not password:
        raise RuntimeError("Configure CONSULTA_DB_SERVER, CONSULTA_DB_USER e CONSULTA_DB_PASS.")

    raw_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    connection_string = _connection_string(config, server, user, password, database)
    group = _optional_int(config.get("pagGrupoClienteCod"))
    for item in wanted:
        check_cancelled()
        try:
            row = _fetch_one_document_with_retry(pyodbc, connection_string, config, item, group)
        except Exception as exc:
            errors.append({"cte": _wanted_label(item), "message": _compact_error(exc)})
            continue
        if row:
            raw_rows.append(row)

    enriched = [{**row, "status": "SQL_CONSULTA_MANUAL"} for row in _dedupe_rows(raw_rows)]
    return SqlConsultaResult(
        rows=enriched,
        source_file="SQL_CONSULTA_MANUAL",
        source={
            **_source_meta(),
            "manualLookupTotal": len(wanted),
            "manualLookupFound": len(enriched),
            "manualLookupErrorCount": len(errors),
            "manualLookupErrors": errors[:MAX_MANUAL_LOOKUP_ERRORS],
        },
    )


def _fetch_one_document_with_retry(
    pyodbc: Any,
    connection_string: str,
    config: dict[str, Any],
    item: dict[str, Any],
    group: int | None,
) -> dict[str, Any] | None:
    attempts = 2 if config.get("retryManualLookup", True) else 1
    for attempt in range(attempts):
        check_cancelled()
        try:
            return _fetch_one_document(pyodbc, connection_string, config, item, group)
        except Exception as exc:
            if attempt + 1 >= attempts or not _should_retry_sql(exc):
                raise
    return None


def _fetch_one_document(
    pyodbc: Any,
    connection_string: str,
    config: dict[str, Any],
    item: dict[str, Any],
    group: int | None,
) -> dict[str, Any] | None:
    connection = pyodbc.connect(
        connection_string,
        timeout=max(1, int(config.get("connectionTimeoutMs") or 15_000) // 1000),
    )
    try:
        cursor = connection.cursor()
        try:
            cursor.timeout = max(1, int(config.get("requestTimeoutMs") or 20_000) // 1000)
        except Exception:
            pass
        with cancellable_cursor(cursor):
            cursor.execute(SQL_BY_DOCUMENT, item["filial"], item["documento"], item["serie"],
                           item["serie"], group, group)
            row = cursor.fetchone()
        if not row:
            return None
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))
    finally:
        connection.close()


def _connection_string(
    config: dict[str, Any],
    server: str,
    user: str,
    password: str,
    database: str,
) -> str:
    parts = [
        "DRIVER={SQL Server}",
        f"SERVER={server}",
        f"UID={user}",
        f"PWD={password}",
    ]
    if database:
        parts.append(f"DATABASE={database}")
    if config.get("encrypt"):
        parts.append("Encrypt=yes")
    else:
        parts.append("Encrypt=no")
    if config.get("trustServerCertificate"):
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts) + ";"


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        mapped = _map_db_row(row)
        filial = _part(mapped.get("FILIAL"))
        serie = _part(mapped.get("SERIE"))
        documento = _part(mapped.get("DOCUMENTO"))
        key = "|".join(part for part in [filial, serie, documento] if part)
        if not filial or not serie or not documento or key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "filial": filial,
                "serie": serie,
                "documento": documento,
                "cte": f"{filial}-{serie}-{documento}",
                "status": "SQL_ULTIMOS_5_DIAS",
                "data": _json_value(mapped.get("DATA")),
                "origem": mapped.get("REM_CIDADE") or mapped.get("LOCCOL") or "",
                "destino": mapped.get("DES_CIDADE") or mapped.get("LOCENT") or "",
                "cteId": mapped.get("CTE_ID") or "",
                "__sql": {"enriched": True, **{key: _json_value(value) for key, value in mapped.items()}},
                **{key: _json_value(value) for key, value in mapped.items()},
            }
        )
    return out


def _wanted_documents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        filial = _optional_int(row.get("filial") or row.get("FILIAL"))
        documento = _optional_int(row.get("documento") or row.get("DOCUMENTO") or row.get("nCT"))
        if filial is None or documento is None:
            continue
        serie = _part(row.get("serie") or row.get("SERIE") or "")
        key = f"{filial}|{serie}|{documento}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"filial": filial, "serie": serie or None, "documento": documento})
    return out


def _wanted_label(item: dict[str, Any]) -> str:
    serie = item.get("serie") or ""
    return "-".join(str(part) for part in [item.get("filial"), serie, item.get("documento")] if str(part or ""))


def _should_retry_sql(exc: Exception) -> bool:
    text = str(exc).lower()
    return "kill state" in text or "(596)" in text or " 596" in text


def _compact_error(exc: Exception) -> str:
    text = re.sub(r"\s+", " ", str(exc)).strip()
    return text[:500]


def _map_db_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "FILIAL": row.get("FILIAL") or "",
        "SERIE": row.get("SERIE") or "",
        "DOCUMENTO": row.get("DOCUMENTO") or "",
        "DATA": row.get("DATA"),
        "VLR_TOTAL": row.get("VLR_TOTAL"),
        "VLR_TAR": row.get("VLR_TAR"),
        "OUTROS": row.get("OUTROS"),
        "FREVAL": row.get("FREVAL"),
        "NMGNRE": row.get("NMGNRE") or "",
        "CTE_ID": row.get("CTE_ID") or "",
        "LOCCOL": row.get("LOCCOL") or "",
        "LOCENT": row.get("LOCENT") or "",
        "OBSCON": row.get("OBSCON") or "",
        "ESTCOL": row.get("ESTCOL") or "",
        "ESTDES": row.get("ESTDES") or "",
        "VLR_FRETE_PESO": row.get("VLR_FRETE_PESO"),
        "REM_CIDADE": row.get("REM_CIDADE") or "",
        "DES_CIDADE": row.get("DES_CIDADE") or "",
        "VEI_CODIGO": row.get("VEI_CODIGO") or "",
        "PEDIDO": row.get("PEDIDO") or "",
        "OBSERVACAO": row.get("OBSERVACAO") or "",
    }


def _source_meta() -> dict[str, Any]:
    today = date.today()
    return {
        "generatedAt": datetime.now().isoformat(),
        "tipoData": "C",
        "pDtIni": date.fromordinal(today.toordinal() - 5).isoformat(),
        "pDtFin": date.fromordinal(today.toordinal() - 1).isoformat(),
    }


def _optional_int(value: Any) -> int | None:
    digits = re.sub(r"\D+", "", str(value or ""))
    return int(digits) if digits else None


def _part(value: Any) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits.lstrip("0") or digits or str(value or "").strip().upper()


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value
