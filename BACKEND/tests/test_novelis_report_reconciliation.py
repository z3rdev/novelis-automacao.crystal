import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from urllib.parse import parse_qs

import httpx
import pytest
from test_novelis_http_batch import Portal, plan_fixture

from app.services.novelis_chamado_http.report_lookup import existing_number
from app.services.novelis_chamado_http.session import HttpChamadosSession
from app.services.novelis_chamado_http.submissions import Submissions


@pytest.mark.parametrize("previous_send", [False, True])
def test_old_cte_opened_today_is_confirmed_and_only_one_save_can_be_sent(tmp_path, monkeypatch, previous_send):
    plan, _ = plan_fixture(tmp_path, count=1)
    row = plan["rows"][0]
    today = datetime.now().astimezone().date()
    row["data"] = (today - timedelta(days=1)).isoformat()
    cte = plan["checked"][0]["cte"]
    portal = Portal({cte: row})
    cfg = {"user": "fixture", "pass": "fixture", "chamadosLogFile": str(tmp_path / "processed.json")}
    if previous_send:
        portal.saved["20261114001559"] = cte
        journal = Submissions(tmp_path, cfg)
        journal.reserve(row, "previous-run")
        journal.finish(row, {"status": "indeterminate", "submitted": True})

    def request(request):
        response = portal.handle(request)
        if request.url.path == "/portal/chamado":
            # The portal accepts the save, with no redirect/number in the response.
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/custom/relatorio_cte_xml_excel":
            period = parse_qs(request.content.decode())
            start = date.fromisoformat("-".join(reversed(period["de"][0].split("/"))))
            end = date.fromisoformat("-".join(reversed(period["ate"][0].split("/"))))
            assert start <= today - timedelta(days=1) and end >= today
        return response

    monkeypatch.setattr("app.services.novelis_chamado_http.session.current_catalog", lambda _: None)
    emit = AsyncMock()

    async def exercise():
        async with HttpChamadosSession(tmp_path, cfg, emit, "reconcile", transport=httpx.MockTransport(request)) as session:
            result = await session.open(row, {**cfg, "evidence": plan["checked"][0]["evidence"]})
            assert result["status"] == ("already_exists" if previous_send else "confirmed")
            assert result["attachments_visible"] is True
            assert result["confirmation_source"] == "portal_report"
            assert (await session.open(row, cfg))["status"] == "already_exists"

    asyncio.run(exercise())
    assert sum(call.url.path == "/portal/chamado" for call in portal.calls) == (0 if previous_send else 1)
    assert len(portal.saved) == 1
    assert Submissions(tmp_path, cfg).reserve(row, "later")["status"] == "confirmed"


def test_cached_ticket_lookup_rejects_a_different_fiscal_key_for_the_same_number():
    target = {"filial": "10", "serie": "10", "documento": "2881", "cteId": "1" * 44}
    older = {"cte": "10-10-2881", "cteId": "2" * 44, "chamadoNumero": "202611140001"}
    assert existing_number([older], target) == ""
    assert existing_number([{**older, "cteId": "1" * 44}], target) == "202611140001"
