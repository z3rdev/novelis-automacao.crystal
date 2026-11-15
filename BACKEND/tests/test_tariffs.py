import asyncio
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.tariffs.models import ZONE, day, decimal, estimate, next_check, project, status
from app.services.tariffs.municipalities import city, portal_cities
from app.services.tariffs.portal import Options, PortalError
from app.services.tariffs.service import TariffService


def raw(**updates):
    return {
        "id": "3113",
        "rota_id": "306",
        "origem": "SP-Pindamonhangaba",
        "destino": "ES-Cariacica",
        "tarifa": "424,00",
        "total": "15.264,00",
        "capacidade": "36",
        "inicio": "01/11/2026",
        "fim": "14/11/2026",
        **updates,
    }


def test_municipalities_preserve_portal_id_and_use_correct_accents_without_fuzzy_guess():
    value = city("es - CARIACICA", "1112")
    assert value["label"] == "ES-Cariacica" and value["portal_id"] == "1112"
    assert value["ibge"] != 1112
    assert city("PB-CABEDELO")["label"] == "PB-Cabedelo"
    assert not city("PB-CADEBELO")["matched"]


def test_validity_is_inclusive_preserves_history_and_never_uses_inconsistent_dates():
    value = project(raw(), [])
    today = day("14/11/2026")
    assert status(day(value["inicio"]), day(value["fim"]), today) == "vigente"
    assert status(day(value["inicio"]), day(value["fim"]), day("15/11/2026")) == "vencida"
    assert not project(raw(inicio="06/09/2022", fim="05/09/2022"), [])["vigenciaValida"]
    assert not project(raw(fim="erro"), [])["vigenciaValida"]
    assert project(raw(fim=""), [])["vigenciaValida"]
    assert next_check([value], datetime(2026, 11, 14, 10, tzinfo=ZONE)) == datetime(
        2026, 11, 15, tzinfo=ZONE
    )
    # Thousands of old records do not cause an immediate refresh loop.
    old = project(raw(inicio="01/11/2022", fim="14/11/2022"), [])
    assert next_check([old], datetime(2026, 11, 14, 10, tzinfo=ZONE)).date() == day("15/11/2026")


def test_decimal_estimate_uses_actual_tonnes_not_vehicle_capacity():
    value = project(raw(), [])
    result = estimate(value, "27,5", day("14/11/2026"))
    assert result["valor"] == "11660.00" and result["toneladas"] == "27.5"
    assert not result["excedeCapacidade"]
    assert estimate(value, "40", day("15/11/2026"))["excedeCapacidade"]
    assert estimate(value, "40", day("15/11/2026"))["status"] == "vencida"
    assert decimal(0) == Decimal(0)
    assert value["valorTotal"] == "15264.00" and value["capacidadeTon"] == "36"
    for invalid in ("0", "-1", "abc", "1e3", "NaN", "100001"):
        with pytest.raises(ValueError):
            estimate(value, invalid)


def test_options_parse_portal_values_separately_from_labels_and_ignore_unrelated_selects():
    parser = Options()
    parser.feed(
        '<select name="other"><option value="secret">X</option></select>'
        '<select name="origem"><option value="1112">ES-Cariacica</option></select>'
        '<select name="destino"><option value="1112">ES-Cariacica</option></select>'
    )
    values = portal_cities(parser.values)
    assert len(values) == 1 and values[0]["portal_id"] == "1112" and values[0]["matched"]


class FakeRepository:
    enabled = True

    def __init__(self):
        self.lease = None
        self.saved = None
        self.message = ""

    def initialize(self):
        pass

    def claim(self, force):
        if self.lease:
            return None
        self.lease = "fixture"
        return self.lease

    def save(self, rows, cities, next_check, lease):
        self.saved = (rows, cities, next_check)
        self.lease = None

    def fail(self, lease, message, **diagnostic):
        self.message = message
        self.lease = None

    def sync_status(self):
        return {"state": "running" if self.lease else "idle"}


def test_shared_claim_prevents_duplicate_collection_and_failure_preserves_old_catalog():
    async def run():
        repo = FakeRepository()
        collector = AsyncMock(return_value=([raw()], {}))
        service = TariffService(SimpleNamespace(), repo, collector)
        await service.refresh(True)
        await service._job
        assert repo.saved[0][0]["idTarifa"] == "3113"
        prior = repo.saved
        service.collector = AsyncMock(side_effect=PortalError("private fixture response"))
        await service.refresh(True)
        await service._job
        assert repo.saved is prior and "private fixture" not in repo.message
        repo.lease = "another computer"
        await service.refresh(True)
        assert service.collector.await_count == 1

    asyncio.run(run())
