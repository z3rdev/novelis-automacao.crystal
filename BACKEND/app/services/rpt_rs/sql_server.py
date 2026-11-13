"""Fetch the report's joined tables through ODBC, scoped to one CT-e."""
import re
from datetime import date, datetime, time
from decimal import Decimal

from app.automation.cancellation import cancellable_cursor, check_cancelled
from app.services.crystal_reports.connection import odbc_connection_string


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def native_query(scope: dict, document) -> tuple[str, tuple]:
    original = scope["sql"]
    before, separator, source = original.partition(" FROM ")
    if not separator or not before.startswith("SELECT "):
        raise ValueError("Plano SQL do relatorio invalido.")
    projection = []
    for column in scope["columns"]:
        if column.get("expression"):
            projection.append("(" + column["expression"] + ")")
        else:
            projection.append(quote(column["alias"]) + "." + quote(column["field"]))
    aliases = {column["alias"] for column in scope["columns"]}
    preferred = ["RODCON"] if scope["name"] == "main" else ["RODNFC", "RODCPL", "RODCON"]
    anchor = next((name for name in preferred if name in aliases), None)
    if anchor is None:
        raise ValueError("Escopo SQL sem tabela de CT-e reconhecida.")
    where = " AND ".join(f"{quote(anchor)}.{quote(field)}=?" for field in ("CODFIL", "SERCON", "CODCON"))
    sql = "SELECT " + ", ".join(projection) + " FROM " + source + " WHERE " + where
    return sql, (document.filial, document.serie, document.documento)


def cell(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (str, int, float, Decimal)):
        return str(value)
    raise ValueError("Tipo SQL de campo ainda nao suportado pelo adaptador rpt-rs.")


def fetch_datasets(scopes: list[dict], database: dict, document) -> tuple[dict, dict]:
    import pyodbc

    datasets, evidence = {}, {}
    try:
        connection = pyodbc.connect(odbc_connection_string(database), timeout=15)
        try:
            connection.timeout = 60
            for scope in scopes:
                check_cancelled()
                sql, parameters = native_query(scope, document)
                with cancellable_cursor(connection.cursor()) as cursor:
                    cursor.execute(sql, *parameters)
                    rows = [[cell(value) for value in row] for row in cursor.fetchall()]
                datasets[scope["name"]] = {"rows": rows}
                evidence[scope["name"]] = {"rows": len(rows), "columns": len(scope["columns"])}
        finally:
            connection.close()
    except pyodbc.Error as error:
        state = str(error.args[0]) if error.args else "unknown"
        if not re.fullmatch(r"[A-Z0-9]{5}", state):
            state = "unknown"
        raise RuntimeError("Consulta SQL do rpt-rs falhou. SQLSTATE " + state) from None
    if not datasets.get("main", {}).get("rows"):
        raise ValueError("Nenhum registro principal encontrado para o CT-e solicitado.")
    return datasets, evidence
