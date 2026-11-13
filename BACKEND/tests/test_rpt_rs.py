import sys
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.crystal_reports.models import DacteRequest
from app.services.rpt_rs.conditions import normalize_condition
from app.services.rpt_rs.model import prepare_model
from app.services.rpt_rs.sql_server import cell, fetch_datasets, native_query


def test_basic_nested_visibility_preserves_false_default_and_else_branch():
    text = "if {T.Mode} = 5 then\nformula = true\nelse\nif {T.Annex} then\nformula = true\nend if\nend if"
    assert normalize_condition(text) == (
        "(If ({T.Mode} = 5) Then (true) Else ((If ({T.Annex}) Then (true) Else (False))))")


def test_basic_membership_becomes_crystal_array():
    assert normalize_condition('if {T.Mode} in array ("C", "F") then\nformula = true\nend if') == (
        '(If ({T.Mode} in ["C", "F"]) Then (true) Else (False))')


def test_crystal_expression_is_preserved():
    text = 'IsNull({T.Qr}) or {T.Qr} = ""'
    assert normalize_condition(text) == text


def test_unknown_basic_statements_produce_a_clear_error():
    with pytest.raises(ValueError, match="Instrucao Basic"):
        normalize_condition('Dim x as Integer\nformula = x')


def test_basic_shared_variable_is_read_before_the_suffix_write():
    assert normalize_condition("shared bRecibo as boolean\nformula = bRecibo\nbRecibo = true") == (
        "Shared BooleanVar bRecibo;\nLocal BooleanVar novelisCondition;\n"
        "novelisCondition := bRecibo;\nbRecibo := true;\nnovelisCondition")


def test_basic_while_printing_scope_is_preserved():
    translated = normalize_condition(
        'whileprintingrecords\nshared CONTROL AS STRING\nif CONTROL <> "S" then\nformula = true\nend if')
    assert translated.startswith("WhilePrintingRecords;\nShared StringVar CONTROL;")
    assert '(If (CONTROL <> "S") Then (true) Else (False))' in translated


def test_symbols_replace_only_model_objects_and_preserve_bounds_and_source():
    def obj(field):
        return {"kind": {"Field": {"data_source": field}}, "bounds": {"width": 120, "height": 100}}

    model = {"report_definition": {"areas": [{"sections": [
        {"objects": [obj("{@F_QRCODE}"), obj("{@F_CODBAR}")]}]}]},
        "data_definition": {"field_definitions": []}}
    adapted, counts = prepare_model(model, b"qr", b"barcode")
    original = model["report_definition"]["areas"][0]["sections"][0]["objects"]
    pictures = adapted["report_definition"]["areas"][0]["sections"][0]["objects"]
    assert all("Field" in item["kind"] for item in original)
    assert all("Picture" in item["kind"] for item in pictures)
    assert pictures[0]["bounds"] == {"width": 100, "height": 100}
    assert pictures[1]["bounds"] == {"width": 120, "height": 100}
    assert counts == {"qr_pictures": 1, "code128_pictures": 1, "normalized_conditions": 0}


def test_sql_server_fetch_uses_native_typed_projection_and_bound_document_parameters():
    scope = {"name": "main", "sql": 'SELECT CAST("RODCON"."CODCON" AS TEXT) FROM "RODCON" AS "RODCON"',
             "columns": [{"alias": "RODCON", "field": "CODCON", "expression": None}]}
    query, parameters = native_query(scope, DacteRequest(filial=2, serie="10", documento=17419))
    assert query.startswith('SELECT "RODCON"."CODCON" FROM ')
    assert query.count("?") == 3 and "17419" not in query
    assert parameters == (2, "10", 17419)


def test_values_keep_decimal_precision_and_iso_dates():
    assert cell(Decimal("12345.67")) == "12345.67"
    assert cell(datetime(2026, 11, 11, 3, 17, tzinfo=UTC)) == "2026-11-11T03:17:00+00:00"
    assert cell(True) == "true" and cell(None) is None


def test_odbc_errors_never_expose_credentials(monkeypatch):
    class DriverError(RuntimeError):
        pass

    def fail(*_args, **_kwargs):
        raise DriverError("PWD=private-test-secret")

    monkeypatch.setitem(sys.modules, "pyodbc", SimpleNamespace(connect=fail, Error=DriverError))
    with pytest.raises(RuntimeError) as caught:
        fetch_datasets([], {"server": "sql", "database": "test", "auth": "windows"}, None)
    assert "private-test-secret" not in str(caught.value)
