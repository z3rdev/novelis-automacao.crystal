"""Check installed SQL configuration with read-only queries and redacted output."""
import argparse
import json
import platform
import re
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace


def diagnose(root: Path) -> dict:
    sys.path.insert(0, str(root / "BACKEND"))
    from app.config.legacy_config import LegacyConfig

    legacy = LegacyConfig(SimpleNamespace(backend_root=root / "BACKEND"))
    config = legacy.consulta_db()
    report = {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "machine": platform.node(),
        "process_bits": struct.calcsize("P") * 8,
        "active_env_exists": (root / "BACKEND/.env").is_file(),
        "refresh_sql": legacy.pendentes()["refreshSql"],
        "sql_enabled": config["enabled"],
        "strict_sql": legacy.pendentes()["strictSql"],
        "configured": {key: bool(str(config.get(key) or "").strip())
                       for key in ("server", "user", "pass", "database")},
        "connected": False,
        "query_objects_readable": False,
    }
    if not all(report["configured"][key] for key in ("server", "user", "pass")):
        return {**report, "reason": "sql_configuration_incomplete"}

    stage = "driver"
    try:
        import pyodbc
        from app.data.consulta_db import _connection_string

        report["legacy_driver_installed"] = "SQL Server" in pyodbc.drivers()
        stage = "connection"
        # Use the application's exact connection settings. Never print the string.
        connection = pyodbc.connect(_connection_string(
            config, config["server"], config["user"], config["pass"], config["database"]), timeout=10)
        try:
            report["connected"] = True
            connection.timeout = 10
            stage = "database"
            cursor = connection.cursor()
            database, access = cursor.execute("SELECT DB_NAME(), HAS_DBACCESS(DB_NAME())").fetchone()
            report["requested_database_opened"] = database.casefold() == config["database"].casefold()
            report["has_dbaccess"] = access == 1
            stage = "query_objects"
            cursor.execute("SELECT TOP (0) FILIAL, SERIE, DOCUMENTO FROM VW_RECEBER_DELLMAR")
            cursor.execute("SELECT TOP (0) CODCON, CODFIL, CTE_ID FROM RODCON")
            report["query_objects_readable"] = True
        finally:
            connection.close()
    except Exception as error:  # noqa: BLE001 -- Redact all driver exception messages.
        # Driver messages can contain account information. Retain only error codes.
        text = str(error)
        report.update(reason="sql_check_failed", stage=stage, error_type=type(error).__name__,
                      sqlstate=(error.args[0] if error.args and re.fullmatch(r"[A-Z0-9]{5}", str(error.args[0]))
                                else None),
                      database_open_error_4060=bool(re.search(r"\b4060\b", text)),
                      session_killed_error_596=bool(re.search(r"\b596\b", text)),
                      login_error_18456=bool(re.search(r"\b18456\b", text)))
        return report
    if config["database"] and not report["requested_database_opened"]:
        return {**report, "reason": "unexpected_database"}
    if not report["sql_enabled"] or not report["refresh_sql"]:
        return {**report, "reason": "sql_disabled"}
    return {**report, "reason": "ok"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = diagnose(args.root.resolve())
    except Exception as error:  # noqa: BLE001 -- Keep credential-bearing tracebacks out of diagnostics.
        report = {"reason": "diagnostic_failed", "error_type": type(error).__name__}
    encoded = json.dumps(report, indent=2, ensure_ascii=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if report.get("reason") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
