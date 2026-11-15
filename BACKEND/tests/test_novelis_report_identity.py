from unittest.mock import AsyncMock

import pytest

from app.automation.flows.novelis_relatorio.steps.novelis_relatorio_cte_xml import (
    NovelisRelatorioCteXmlFlow,
)


def test_same_series_and_number_with_different_access_key_stays_pending(tmp_path):
    flow = NovelisRelatorioCteXmlFlow(tmp_path, AsyncMock())
    target = {"filial": "10", "serie": "10", "documento": "2881", "cteId": "1" * 44}
    old = {**target, "cteId": "2" * 44, "chamadoNumero": "202611140001", "andamento": "Solucionado"}
    old["key"] = flow._row_key(old)
    kept, existing = flow._split_existing([target], {old["key"]: old}, {"10|2881": old})
    assert len(kept) == 1 and not existing
    assert kept[0]["__novelis"] == {"prechecked": True, "alreadyExists": False}


@pytest.mark.parametrize("report_key,number,exists", [("1" * 44, "202611140001", True), ("1" * 44, "", False), ("legacy-id", "202611140001", True)])
def test_exact_keys_and_legacy_number_fallback_require_an_opened_ticket(tmp_path, report_key, number, exists):
    flow = NovelisRelatorioCteXmlFlow(tmp_path, AsyncMock())
    target = {"filial": "10", "serie": "10", "documento": "2881", "cteId": "1" * 44}
    report = {**target, "cteId": report_key, "chamadoNumero": number}
    report["key"] = flow._row_key(report)
    kept, existing = flow._split_existing([target], {report["key"]: report}, {"10|2881": report})
    assert bool(existing) is exists
    assert bool(kept) is not exists
