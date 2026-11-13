import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def helper():
    path = Path(__file__).resolve().parents[2] / "scripts/diagnose-consulta-sql.py"
    spec = importlib.util.spec_from_file_location("diagnose_consulta", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure(root):
    backend = root / "BACKEND"
    backend.mkdir()
    (backend / ".env").write_text(
        "CONSULTA_DB_SERVER=private-host\nCONSULTA_DB_DATABASE=test-db\n"
        "CONSULTA_DB_USER=private-user\nCONSULTA_DB_PASS=private-password\n"
        "CONSULTA_DB_FALLBACK_ENABLED=true\n", encoding="utf-8")


def test_sql_diagnostic_never_exposes_driver_exception_or_credentials(tmp_path, monkeypatch):
    configure(tmp_path)

    def fail(*_args, **_kwargs):
        raise RuntimeError("42000", "private-user private-password private-host (4060)")

    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(
        connect=fail, drivers=lambda: ["SQL Server"]))
    result = helper().diagnose(tmp_path)
    encoded = json.dumps(result)
    assert result["database_open_error_4060"] is True
    assert result["sqlstate"] == "42000"
    assert all(value not in encoded for value in ("private-user", "private-password", "private-host"))


def test_sql_diagnostic_uses_read_only_statements_and_closes_connection(tmp_path, monkeypatch):
    configure(tmp_path)
    statements = []
    state = {"closed": False}

    class Connection:
        def cursor(self):
            return self

        def execute(self, statement):
            statements.append(statement)
            return self

        def fetchone(self):
            return "test-db", 1

        def close(self):
            state["closed"] = True

    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(
        connect=lambda *_args, **_kwargs: Connection(), drivers=lambda: ["SQL Server"]))
    result = helper().diagnose(tmp_path)
    assert result["reason"] == "ok" and result["query_objects_readable"]
    assert state["closed"] and len(statements) == 3
    assert all(statement.startswith("SELECT ") for statement in statements)

    with (tmp_path / "BACKEND/.env").open("a", encoding="utf-8") as output:
        output.write("PENDENTES_REFRESH_SQL=false\n")
    result = helper().diagnose(tmp_path)
    assert result["connected"] is True
    assert result["reason"] == "sql_disabled"


def test_missing_sql_configuration_is_reported_without_attempting_connection(tmp_path):
    result = helper().diagnose(tmp_path)
    assert result["reason"] == "sql_configuration_incomplete"
    assert result["connected"] is False
