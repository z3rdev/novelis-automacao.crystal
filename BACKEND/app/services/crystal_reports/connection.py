from app.config.legacy_config import LegacyConfig
from app.services.crystal_reports.models import DacteRequest


def report_database(config: LegacyConfig) -> dict:
    fallback = (
        config.consulta_db()
        if config.get("CRYSTAL_DB_USE_CONSULTA", "true").lower() == "true"
        else {}
    )
    server = config.get("CRYSTAL_DB_SERVER").strip()
    host, instance, port = (
        config.get("CRYSTAL_DB_" + key).strip() for key in ("HOST", "INSTANCE", "PORT")
    )
    if not server and host:
        if port and (not port.isdecimal() or not 1 <= int(port) <= 65535):
            raise ValueError("CRYSTAL_DB_PORT precisa estar entre 1 e 65535.")
        server = host + ("\\" + instance if instance else "") + ("," + port if port else "")
    auth = config.get("CRYSTAL_DB_AUTH", "sql").lower()
    if auth not in {"sql", "windows"}:
        raise ValueError("CRYSTAL_DB_AUTH precisa ser sql ou windows.")
    return {
        "server": server or str(fallback.get("server") or ""),
        "database": config.get("CRYSTAL_DB_DATABASE") or str(fallback.get("database") or ""),
        "user": ""
        if auth == "windows"
        else config.get("CRYSTAL_DB_USER") or str(fallback.get("user") or ""),
        "password": ""
        if auth == "windows"
        else config.get("CRYSTAL_DB_PASS") or str(fallback.get("pass") or ""),
        "auth": auth,
    }


def database_configured(database: dict) -> bool:
    return bool(
        database["server"]
        and database["database"]
        and (database["auth"] == "windows" or (database["user"] and database["password"]))
    )


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def odbc_connection_string(database: dict) -> str:
    parts = [
        "DRIVER={SQL Server}",
        "SERVER=" + _odbc_value(database["server"]),
        "DATABASE=" + _odbc_value(database["database"]),
    ]
    if database["auth"] == "windows":
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend(
            ["UID=" + _odbc_value(database["user"]), "PWD=" + _odbc_value(database["password"])]
        )
    return ";".join(parts)


def check_database(database: dict, document: DacteRequest | None = None) -> dict:
    if not database_configured(database):
        return {
            "status": "pending",
            "message": "Configure CRYSTAL_DB_* ou CONSULTA_DB_* nesta maquina.",
        }
    try:
        import pyodbc
    except ImportError:
        return {"status": "error", "message": "Driver Python ODBC nao instalado."}
    try:
        with pyodbc.connect(odbc_connection_string(database), timeout=10) as connection:
            connection.timeout = 15
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            if document:
                cursor.execute(
                    "SELECT TOP (1) CTE_ID FROM RODCON WHERE CODFIL=? AND SERCON=? AND CODCON=?",
                    document.filial,
                    document.serie,
                    document.documento,
                )
                row = cursor.fetchone()
                return {"status": "ok" if row else "not_found", "document_found": bool(row)}
        return {"status": "ok"}
    except (pyodbc.Error, OSError):
        return {
            "status": "error",
            "message": "Falha ao consultar o banco com a configuracao local.",
        }
