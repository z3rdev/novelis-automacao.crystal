import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.data.consulta_db import _dedupe_rows
from app.data.cte_fields import enrich
from app.domain.models import RunStartRequest
from app.services.chamado_message import DEFAULT_MESSAGE, render_message
from app.services.tariffs.audit import annotate_plan, check, message_fields
from app.services.tariffs.models import project


def sql(**changes):
    return {
        "FILIAL": 8,
        "SERIE": 10,
        "DOCUMENTO": 1559,
        "REM_CIDADE": "JOAO PESSOA",
        "DES_CIDADE": "CABEDELO",
        "ESTCOL": "PB",
        "ESTDES": "PB",
        "DATA": "2026-11-14T13:22:00",
        "VLR_TAR": 4644,
        "FREVAL": 159.3,
        "OUTROS": 1200.83,
        "VLR_TOTAL": 6004.13,
        "OBSERVACAO": "PERCURSO: 6854000 ID: 217903",
        **changes,
    }


def tariff(identifier="666318", capacity="30", **changes):
    return project(
        {
            "id": identifier,
            "rota_id": "952",
            "origem": "PB-João Pessoa",
            "destino": "PB-Cabedelo",
            "tarifa": "154,80",
            "total": "4.644,00" if capacity == "30" else "4.179,60",
            "capacidade": capacity,
            "faturamento": "13.254.104/0001-74",
            "inicio": "15/07/2026",
            "fim": "31/12/2026",
            **changes,
        },
        [],
    )


def test_sql_rows_parse_observation_without_confusing_order_id_and_tariff_id():
    raw = sql(OBSERVACAO="PERCURSO: 6854000 | ID=217903 | TON: 30 | ID TARIFARIO: 666318")
    row = _dedupe_rows([raw])[0]
    assert row["ton"] == 30 and row["tonRaw"] == "30"
    assert row["id"] == "217903" and row["idTarifarioObservacao"] == "666318"
    assert row["percurso"] == "6854000" and row["vlrTar"] == 4644
    assert row["OBSERVACAO"] == raw["OBSERVACAO"]


@pytest.mark.parametrize(
    "text,ton",
    [
        ("TON 30", 30),
        ("TON: 30", 30),
        ("30 TON", 30),
        ("30TON", 30),
        ("27,5 TON", 27.5),
        ("36 toneladas", 36),
        ("TONELADAS: 36", 36),
    ],
)
def test_tonnage_unit_can_appear_before_or_after_the_number(text, ton):
    from app.data.consulta_reader import parse_observacao

    assert parse_observacao("ID 217903 | " + text)["ton"] == ton


def test_real_postfix_example_reads_tonnage_instead_of_tax_amount():
    observed = (
        "ID 217903 | 30 TON - ROTA NÃO POSSUI PEDAGIO\nTotal Aproximado de Impostos : 1.645,14;"
    )
    row = _dedupe_rows([sql(OBSERVACAO=observed, OBSCON=observed)])[0]
    result = check(row, [tariff("666788", "27"), tariff()])
    assert row["ton"] == 30 and row["id"] == "217903"
    assert result["status"] == "conferido" and result["tonObservacao"] == "30"
    assert result["selecionada"]["idTarifa"] == "666318" and result["tonConfere"] is True
    assert observed == row["OBSERVACAO"]


def test_missing_ton_is_not_invented_in_audit_but_unique_freight_identifies_the_contract_for_message():
    raw = sql()
    audit = check(raw, [tariff("666788", "27"), tariff()])
    assert audit["selecionada"]["idTarifa"] == "666318" and audit["criterio"] == "frete_sql"
    assert audit["tonObservacao"] is None and audit["status"] == "dados_incompletos"
    row = message_fields(_dedupe_rows([raw])[0], audit)
    message = render_message(row, "Operador de teste", DEFAULT_MESSAGE)
    assert "TON: 30" in message and "ID: 217903" in message and "ID TARIFARIO: 666318" in message
    assert row["VLR_TAR"] == raw["VLR_TAR"] and row["OBSERVACAO"] == raw["OBSERVACAO"]
    assert check(row, [tariff()])["tonObservacao"] is None


def test_matching_and_divergence_use_contract_capacity_and_base_freight_not_invoice_total():
    values = [tariff("666788", "27"), tariff()]
    result = check(sql(OBSERVACAO="TON 30"), values)
    assert (
        result["status"] == "conferido" and result["freteConfere"] and result["composicaoConfere"]
    )
    assert result["totalReferencia"] == "6004.13"
    conflict = check(sql(OBSERVACAO="TON 27"), values)
    assert conflict["status"] == "divergente"
    assert conflict["selecionada"]["idTarifa"] == "666788" and conflict["tonConfere"]
    changed = check(sql(OBSERVACAO="TON 30", VLR_TAR=4644.01, VLR_TOTAL=6004.14), [tariff()])
    assert changed["status"] == "divergente" and changed["diferencaFrete"] == "0.01"
    assert changed["tonConfere"] and not changed["freteConfere"]


def test_same_capacity_uses_greatest_numeric_id_regardless_of_catalog_order():
    result = check(sql(OBSERVACAO="TON 30"), [tariff(), tariff("666319")])
    assert result["status"] == "conferido" and result["selecionada"]["idTarifa"] == "666319"
    assert result["criterio"] == "maior_id_mesma_ton"
    for values in ([tariff("9"), tariff("10")], [tariff("10"), tariff("9")]):
        assert check(sql(OBSERVACAO="30 TON"), values)["selecionada"]["idTarifa"] == "10"


def test_latest_id_with_correct_tonnage_wins_over_older_exact_freight_match():
    values = [tariff("666311"), tariff("666552", total="4.700,00"), tariff("999999", "27")]
    row = sql(OBSERVACAO="30 TON ID TARIFARIO: 666311")
    result = check(row, values)
    assert result["selecionada"]["idTarifa"] == "666552"
    assert result["tonConfere"] and not result["freteConfere"]
    assert result["status"] == "divergente" and result["diferencaFrete"] == "-56.00"
    message = message_fields(row, result)
    assert message["idTarifario"] == "666552"
    assert message["idTarifarioObservacao"] == "666311"
    assert message["VLR_TAR"] == row["VLR_TAR"] and message["OBSERVACAO"] == row["OBSERVACAO"]


def test_vila_velha_example_selects_666552_among_five_route_contracts():
    values = [
        tariff(
            identifier, capacity, origem="ES-Vila Velha", destino="SP-Pindamonhangaba", total=total
        )
        for identifier, capacity, total in (
            ("666311", "30", "7.014,30"),
            ("666552", "30", "7.014,30"),
            ("666605", "34", "7.949,54"),
            ("666734", "27", "6.312,87"),
            ("666883", "27", "6.312,87"),
        )
    ]
    result = check(
        sql(
            REM_CIDADE="VILA VELHA",
            DES_CIDADE="PINDAMONHANGABA",
            ESTCOL="ES",
            ESTDES="SP",
            OBSERVACAO="ID 217686 | 30 TON",
            VLR_TAR=7014.30,
            FREVAL=130.58,
            OUTROS=974.30,
            VLR_TOTAL=8119.18,
        ),
        values,
    )
    assert result["selecionada"]["idTarifa"] == "666552"
    assert result["status"] == "conferido" and result["tonConfere"]
    assert result["totalReferencia"] == "8119.18"


def test_larger_ineligible_ids_and_wrong_tonnages_never_override_the_right_contract():
    values = [
        tariff("666552"),
        tariff("999999", "27"),
        tariff("999998", fim="13/11/2026"),
        tariff("999997", inicio="15/11/2026"),
        tariff("999996", origem="PB-Cabedelo"),
        tariff("999995", faturamento="99.999.999/0001-99"),
    ]
    result = check(
        sql(OBSERVACAO="30 TON", CTE_ID="25261113254104000840570100000015591000015592"), values
    )
    assert result["selecionada"]["idTarifa"] == "666552"
    unmatched = check(sql(OBSERVACAO="35 TON"), values)
    assert unmatched["selecionada"] is None and unmatched["status"] == "sem_tarifa"


def test_duplicate_greatest_id_is_not_resolved_by_arbitrary_catalog_order():
    result = check(sql(OBSERVACAO="30 TON"), [tariff("666552"), tariff("666552", rota_id="953")])
    assert result["selecionada"] is None and result["status"] == "ambiguo"
    assert result["criterio"] == "maior_id_duplicado"


def test_old_automatic_match_is_not_reused_when_new_catalog_becomes_ambiguous():
    first = message_fields(sql(), check(sql(), [tariff()]))
    assert first["idTarifario"] == "666318" and first["tonRaw"] == "30"
    next_check = check(first, [tariff(), tariff("666319")])
    assert next_check["status"] == "ambiguo"
    changed = message_fields(first, next_check)
    assert changed["idTarifario"] is None and changed["ton"] is None
    assert changed["id"] == "217903"


def test_wrong_company_dates_and_reverse_route_are_not_used():
    key = "26" + "2611" + "13254104000840" + "57" + "010" + "000001559" + "1" + "00001559" + "2"
    row = sql(CTE_ID=key, OBSERVACAO="TON 30")
    assert len(key) == 44
    for value in [
        tariff(faturamento="99.999.999/0001-99"),
        tariff(fim="13/11/2026"),
        tariff(inicio="15/11/2026"),
        tariff(origem="PB-Cabedelo", destino="PB-João Pessoa"),
    ]:
        assert check(row, [value])["status"] == "sem_tarifa"


def test_observacao_has_priority_and_obscon_is_a_fallback():
    row = enrich(sql(OBSERVACAO="ID 217903", OBSCON="TON=30"))
    assert row["tonObservacaoOriginal"] == "30"
    assert enrich(sql(OBSERVACAO="TON 27", OBSCON="TON 30"))["tonObservacaoOriginal"] == "27"


def test_plan_and_message_keep_divergence_as_warning_without_removing_ready_ctes(
    tmp_path, monkeypatch
):
    from app.automation.flows.novelis_chamados.steps.chamado_novelis import ChamadoNovelisFlow

    row = _dedupe_rows([sql(OBSERVACAO="TON 30 ID 217903")])[0]
    audit = check(row, [tariff("666318", total="4.700,00")])
    assert audit["status"] == "divergente"
    monkeypatch.setattr(
        "app.services.tariffs.audit.TariffAuditService",
        lambda config: SimpleNamespace(rows=lambda rows: {"8-10-1559": audit}),
    )
    plan = {"checked": [{"row": row}], "prontosChamado": ["8-10-1559"]}
    assert annotate_plan(plan, SimpleNamespace())["prontosChamado"] == ["8-10-1559"]
    source = tmp_path / "plan.json"
    source.write_text(json.dumps({"rows": [message_fields(row, audit)]}), encoding="utf-8")
    run = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.automation.flows.novelis_chamados.steps.chamado_novelis.NovelisFlow.run", run
    )
    emit = AsyncMock()
    result = asyncio.run(
        ChamadoNovelisFlow(tmp_path, emit).run(
            None, {"sourceJson": str(source), "ctes": "8-10-1559"}, RunStartRequest(), "fixture"
        )
    )
    assert (
        run.await_count == 1
        and result[0]["idTarifario"] == "666318"
        and str(result[0]["ton"]) == "30"
    )
    assert result[0]["tariffAudit"]["tonObservacao"] == "30"
    assert any(
        call.kwargs.get("kind") == "chamado_novelis.tarifa_alerta" for call in emit.await_args_list
    )
