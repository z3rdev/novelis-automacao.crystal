import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.automation.flows.pendentes.controles import xml_batch, xml_keys
from app.automation.flows.sefaz_xml.steps.xml_sefaz import XmlSefazFlow
from app.domain.models import RunStartRequest
from app.services.hub_views import run_view

KEY = "35260112345678000199570100000231671123456780"


def row(cte, key="", **fields):
    return {**dict(zip(("filial", "serie", "documento"), cte.split("-"))), "cteId": key, **fields}


def batch(rows):
    return {
        "checked": [{"cte": cte, "row": value} for cte, value in rows.items()],
        "rows": list(rows.values()),
        "faltandoXml": list(rows),
    }


def test_only_missing_keys_are_queried_and_fresh_target_reaches_download(monkeypatch, tmp_path):
    known = row("2-10-10402", KEY)
    missing = row("1-10-23167")
    query = Mock(
        return_value=SimpleNamespace(rows=[{**missing, "cteId": KEY, "CTEAUT": "S"}], source={})
    )
    monkeypatch.setattr(xml_keys, "fetch_rows_by_documents", query)
    targets = []

    async def download(browser, config, request, run_id):
        # The persisted plan is deliberately absent. The recovered SQL row is authoritative.
        targets.append(XmlSefazFlow(tmp_path, AsyncMock())._resolve_target(config, request))

    monkeypatch.setattr(xml_batch, "XmlSefazFlow", lambda *_: SimpleNamespace(run=download))
    flow = SimpleNamespace(
        cwd=tmp_path,
        emit=AsyncMock(),
        legacy_config=SimpleNamespace(consulta_db=lambda: {"enabled": True}),
    )
    plan = batch({"2-10-10402": known, "1-10-23167": missing})
    asyncio.run(
        xml_batch.run_xml_batch(
            flow, None, {}, plan, RunStartRequest(), "run", {}, tmp_path / "absent.json"
        )
    )
    assert query.call_args.args[1] == [missing]
    assert [target["cte"] for target in targets] == ["2-10-10402", "1-10-23167"]
    assert all(target["cteId"] == KEY for target in targets)
    assert missing["cteId"] == ""


def test_rodopar_without_key_is_explained_and_other_xmls_continue(monkeypatch, tmp_path):
    missing = row("1-10-26021", CTEAUT="N", CTEPRO=None)
    query = Mock(return_value=SimpleNamespace(rows=[missing], source={}))
    monkeypatch.setattr(xml_keys, "fetch_rows_by_documents", query)
    download = AsyncMock()
    monkeypatch.setattr(xml_batch, "XmlSefazFlow", lambda *_: SimpleNamespace(run=download))
    emit = AsyncMock()
    flow = SimpleNamespace(
        cwd=tmp_path,
        emit=emit,
        legacy_config=SimpleNamespace(consulta_db=lambda: {"enabled": True}),
    )
    plan = batch({"1-10-26021": missing, "1-10-23167": row("1-10-23167", KEY)})
    with pytest.raises(RuntimeError, match="CTEAUT=N"):
        asyncio.run(
            xml_batch.run_xml_batch(
                flow,
                None,
                {},
                plan,
                RunStartRequest(),
                "run",
                {"stopOnError": False},
                tmp_path / "plan.json",
            )
        )
    download.assert_awaited_once()
    assert download.await_args.args[1]["ctes"] == "1-10-23167"
    assert emit.await_args.kwargs["payload"] == {
        "total": 2,
        "done": 1,
        "failed": 1,
        "failedCtes": ["1-10-26021"],
    }


def test_xml_failure_remains_visible_after_later_downloads_and_file_check():
    events = [
        {"kind": "xml_sefaz.progress", "payload": {"cte": "1-10-26021", "current": 1, "total": 2}},
        {
            "kind": "xml_sefaz.error",
            "message": "CT-e sem chave no Rodopar",
            "payload": {"cte": "1-10-26021"},
        },
        {"kind": "xml_sefaz.progress", "payload": {"cte": "1-10-23167", "current": 2, "total": 2}},
        {"kind": "xml_sefaz.saved", "payload": {"cte": "1-10-23167"}},
        {"kind": "pendentes.plan", "payload": {"total": 13}},
    ]
    view = run_view({"id": "run", "flow": "pendentes", "status": "failed"}, events)
    xml = next(stage for stage in view["stages"] if stage["id"] == "xml")
    assert (xml["state"], xml["done"], xml["total"]) == ("falhou", 1, 2)
    assert (view["etapaAtual"], view["cteAtual"], view["processados"], view["total"]) == (
        "xml",
        "1-10-26021",
        1,
        2,
    )


def test_batch_summary_recovers_failure_after_older_events_are_trimmed():
    view = run_view(
        {"id": "run", "flow": "pendentes", "status": "failed"},
        [
            {
                "kind": "xml_sefaz.batch_failed",
                "payload": {"total": 5, "done": 4, "failedCtes": ["1-10-26021"]},
            },
            {"kind": "pendentes.plan", "payload": {"total": 13}},
        ],
    )
    assert view["etapaAtual"] == "xml" and view["processados"] == 4 and view["total"] == 5
