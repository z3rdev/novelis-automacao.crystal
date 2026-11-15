import sys
from types import SimpleNamespace

import pytest

from app.data.consulta_db import fetch_last_5_days_rows, fetch_rows_by_documents


def test_rodcon_observation_lookup_uses_the_full_document_identity():
    from app.data.consulta_db import SQL_LAST_N_DAYS,SQL_BY_DOCUMENT
    for query in (SQL_LAST_N_DAYS,SQL_BY_DOCUMENT):
        assert "RC.CODFIL = R.FILIAL" in query
        assert "RC.SERCON = R.SERIE" in query
        assert "RC.CODCON = R.DOCUMENTO" in query


@pytest.mark.parametrize("fail_stage", ["execute", "fetchall"])
def test_daily_query_reopens_connection_once_after_killed_session(monkeypatch, fail_stage):
    state = _daily_connections(monkeypatch, failures=1, fail_stage=fail_stage)
    result = fetch_last_5_days_rows({"server": "sql", "user": "usr", "pass": "pwd"}, 1)
    assert result.rows == []
    assert result.source_file == "SQL_ULTIMOS_1_DIAS"
    assert state.connections == state.closed == 2
    assert state.parameters == [(0, None, None), (0, None, None)]


def test_daily_query_preserves_error_after_bounded_retry(monkeypatch):
    state = _daily_connections(monkeypatch, failures=10)
    with pytest.raises(Exception, match="596"):
        fetch_last_5_days_rows({"server": "sql", "user": "usr", "pass": "pwd"})
    assert state.connections == state.closed == 2


def test_daily_query_does_not_retry_database_access_error(monkeypatch):
    state = _daily_connections(monkeypatch, failures=10, error="Cannot open database (4060)")
    with pytest.raises(Exception, match="4060"):
        fetch_last_5_days_rows({"server": "sql", "user": "usr", "pass": "pwd"})
    assert state.connections == state.closed == 1


@pytest.mark.parametrize("days,offset", [(0, 0), (5, -4), (10, -9), (20, -19), (30, -29)])
def test_periods_include_today_and_preserve_zero_for_current_day(monkeypatch, days, offset):
    state = _daily_connections(monkeypatch, failures=0)
    fetch_last_5_days_rows({"server": "sql", "user": "usr", "pass": "pwd"}, days)
    assert state.parameters == [(offset, None, None)]


def test_custom_period_passes_both_dates_as_sql_parameters(monkeypatch):
    from datetime import date, timedelta
    state = _daily_connections(monkeypatch, failures=0)
    start, end = date.today() - timedelta(days=8), date.today() - timedelta(days=2)
    fetch_last_5_days_rows({"server": "sql", "user": "usr", "pass": "pwd"}, 0, start, end)
    assert state.parameters == [(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), None, None)]
    assert "DATEADD" not in state.query
    assert "BETWEEN CONVERT(date, ?, 112) AND CONVERT(date, ?, 112)" in state.query


def _daily_connections(monkeypatch, failures, fail_stage="execute", error="Session in kill state (596)"):
    state = SimpleNamespace(connections=0, closed=0, parameters=[])

    class Connection:
        description = (("FILIAL",),)

        def __init__(self, number):
            self.number = number

        def cursor(self):
            return self

        def execute(self, _query, *parameters):
            state.query = _query
            state.parameters.append(parameters)
            if fail_stage == "execute" and self.number <= failures:
                raise RuntimeError(error)

        def fetchall(self):
            if fail_stage == "fetchall" and self.number <= failures:
                raise RuntimeError(error)
            return []

        def close(self):
            state.closed += 1

    def connect(*_args, **_kwargs):
        state.connections += 1
        return Connection(state.connections)

    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(connect=connect))
    return state


def test_manual_lookup_retries_killed_sql_session(monkeypatch):
    state = SimpleNamespace(attempts={}, connections=0, closed=0)

    def connect(_connection_string, timeout):
        state.connections += 1
        return FakeConnection(state, {(2, "10", 10402): 1})

    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(connect=connect))

    result = fetch_rows_by_documents(
        {"server": "sql", "user": "usr", "pass": "pwd"},
        [{"filial": "2", "serie": "10", "documento": "10402"}],
    )

    assert result.rows[0]["cteId"] == _cte_id(2, 10402)
    assert result.source["manualLookupErrorCount"] == 0
    assert state.attempts[(2, "10", 10402)] == 2
    assert state.connections == 2
    assert state.closed == 2


def test_manual_lookup_keeps_partial_results_after_document_failure(monkeypatch):
    state = SimpleNamespace(attempts={}, connections=0, closed=0)

    def connect(_connection_string, timeout):
        state.connections += 1
        return FakeConnection(state, {(9, "10", 287): 99})

    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(connect=connect))

    result = fetch_rows_by_documents(
        {"server": "sql", "user": "usr", "pass": "pwd"},
        [
            {"filial": "2", "serie": "10", "documento": "10402"},
            {"filial": "9", "serie": "10", "documento": "287"},
        ],
    )

    assert [row["documento"] for row in result.rows] == ["10402"]
    assert result.source["manualLookupErrorCount"] == 1
    assert result.source["manualLookupErrors"][0]["cte"] == "9-10-287"


class FakeConnection:
    def __init__(self, state, failing_attempts):
        self.state = state
        self.failing_attempts = failing_attempts

    def cursor(self):
        return FakeCursor(self.state, self.failing_attempts)

    def close(self):
        self.state.closed += 1


class FakeCursor:
    description = (("FILIAL",), ("SERIE",), ("DOCUMENTO",), ("CTE_ID",))

    def __init__(self, state, failing_attempts):
        self.state = state
        self.failing_attempts = failing_attempts
        self.row = None
        self.timeout = 0

    def execute(self, _query, filial, documento, serie_a, _serie_b, _group_a, _group_b):
        key = (filial, serie_a, documento)
        attempt = self.state.attempts.get(key, 0) + 1
        self.state.attempts[key] = attempt
        if attempt <= self.failing_attempts.get(key, 0):
            raise RuntimeError("Cannot continue the execution because the session is in the kill state. (596)")
        self.row = (filial, serie_a or "10", documento, _cte_id(filial, documento))

    def fetchone(self):
        return self.row


def _cte_id(filial, documento):
    return f"CTe35260813254104000255570100000{filial}{documento:09d}"
