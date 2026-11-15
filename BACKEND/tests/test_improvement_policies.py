import asyncio
import os
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.api.routers.hub import StartRequest
from app.domain.models import RunStartRequest
from app.domain.consultation_period import validate_period
from app.automation.flows.pendentes.controles.execution_scope import scoped_config
from app.automation.flows.novelis_chamados.steps.novelis import NovelisFlow
from app.infrastructure.operations_store import OperationsStore
from app.services.chamado_message import validate_template
from app.services.local_document_retention import clean_local_documents, LocalDocumentRetention
from app.services.message_configuration import read, save
from app.services.hub_views import chamado_view


@pytest.mark.parametrize("start,end", [(None, date.today()), (date.today(), None),
    (date.today(), date.today() - timedelta(days=1)),
    (date.today() - timedelta(days=31), date.today()),
    (date.today(), date.today() + timedelta(days=1))])
def test_custom_period_rejects_invalid_dates_in_both_api_contracts(start, end):
    with pytest.raises(ValueError):
        validate_period(start, end)
    with pytest.raises(ValidationError):
        StartRequest(dataInicio=start, dataFim=end)
    with pytest.raises(ValidationError):
        RunStartRequest(consulta_data_inicio=start, consulta_data_fim=end)


def test_custom_period_keeps_both_inclusive_dates():
    start, end = date.today() - timedelta(days=30), date.today() - timedelta(days=2)
    body = StartRequest(dataInicio=start, dataFim=end)
    assert body.range_options() == {"date_start": start, "date_end": end}


@pytest.mark.parametrize("status,expected", [("Pendente", "em_analise"), ("Solucionado", "solucionado"), ("Encerrado", "solucionado"), ("Em análise", "em_analise"), ("Aberto", "aberto")])
def test_real_portal_status_takes_precedence_over_legacy_ticket_exists_marker(status, expected):
    row = chamado_view({"cte": "2-10-123", "chamado": "fixture", "aberturaNovelis": "SOLUCIONADO",
                        "andamento": status, "abertoEm": "2026-11-13T08:00:00"})
    assert row["andamento"] == expected
    assert row["aberturaNovelis"] == "2026-11-13T08:00:00"


def test_receipt_only_scope_does_not_execute_pdf_xml_or_open_tickets():
    config = scoped_config({}, RunStartRequest(execution_scope="comprovantes"))
    assert config["skipPdf"] and config["skipXml"] and config["skipNovelis"]
    assert config["skipComprovantes"] is False


@pytest.mark.parametrize("value", ["{cte.__class__}", "{cte[0]}", "{cte!r}", "{cte:>10}", "{senha}", "{", "   "])
def test_templates_reject_expressions_unknown_fields_and_invalid_format(value):
    with pytest.raises(ValueError):
        validate_template(value)


def test_custom_message_renders_real_data_and_preserves_complement_fields(tmp_path):
    flow = NovelisFlow(tmp_path, None)
    data = {"filial": 2, "serie": "10", "documento": 123, "cteOrigem": "2-10-120", "isCteComplementarFrete": True}
    output = flow.build_chamado_message(data, "Operador", "CTE {cte}; origem {cteOrigem}; {assinatura}")
    assert output == "CTE 2-10-123; origem 2-10-120; Operador"
    assert "CTE COMPLEMENTAR" in flow.build_chamado_message(data, "Operador")
    assert "N CTE DE ORIGEM: 2-10-120" in flow.build_chamado_message(data, "Operador")


def test_message_and_receipt_policy_are_persisted_without_affecting_credentials(tmp_path):
    store = OperationsStore(tmp_path / "preferences.sqlite")
    store.initialize()
    class Config:
        values = {"PRIVATE_PASS": "fixture-only"}
        def get(self, key):
            return self.values.get(key, "")
    config = Config()
    value = read(config)
    assert value["allow_missing_receipt"] is False
    value.update(allow_missing_receipt=True, message="CT-e {cte}\n{assinatura}")
    save(config, store, value)
    assert read(config) == value
    assert store.preferences()["NOVELIS_CHAMADO_ALLOW_MISSING_COMPROVANTE"] == "true"
    assert "PRIVATE_PASS" not in store.preferences()
    store.close()


def test_weekly_retention_deletes_only_old_local_pdf_xml_and_supports_dry_run(tmp_path):
    now = datetime(2026, 11, 18, 12, tzinfo=timezone(timedelta(hours=-3)))
    directory = tmp_path / "runtime/reports/dacte"
    directory.mkdir(parents=True)
    old = directory / "old.pdf"
    current = directory / "current.xml"
    other = directory / "keep.json"
    foreign = tmp_path / "archive/old.pdf"
    foreign.parent.mkdir()
    for path in (old, current, other, foreign):
        path.write_text("fixture")
        os.utime(path, (now.timestamp() - 10 * 86400,) * 2)
    os.utime(current, (now.timestamp(),) * 2)
    preview = clean_local_documents(tmp_path, tmp_path / "runtime", now=now, dry_run=True)
    assert preview["eligible"] == 1 and old.exists()
    result = clean_local_documents(tmp_path, tmp_path / "runtime", now=now)
    assert result["deleted"] == 1 and not old.exists()
    assert all(path.exists() for path in (current, other, foreign))


def test_retention_skips_busy_runs_and_can_be_disabled(tmp_path, monkeypatch):
    from app.services import local_document_retention as retention
    clean = Mock()
    monkeypatch.setattr(retention, "clean_local_documents", clean)
    class Automation:
        _control_lock = asyncio.Lock()
        async def current(self): return SimpleNamespace(status="running")
    settings = SimpleNamespace(backend_root=tmp_path / "BACKEND", storage_dir=tmp_path / "runtime")
    service = LocalDocumentRetention(settings, SimpleNamespace(get=lambda _: "true"), Automation())
    asyncio.run(service.tick())
    service.config = SimpleNamespace(get=lambda _: "false")
    asyncio.run(service.tick())
    clean.assert_not_called()


def test_mapped_network_drive_is_never_cleaned(tmp_path, monkeypatch):
    from app.services import local_document_retention as retention
    directory = tmp_path / "runtime/reports/dacte"
    directory.mkdir(parents=True)
    path = directory / "old.pdf"
    path.write_text("fixture")
    os.utime(path, (0, 0))
    monkeypatch.setattr(retention, "_remote_drive", lambda _: True)
    result = retention.clean_local_documents(tmp_path, tmp_path / "runtime")
    assert result["deleted"] == 0 and path.exists()
