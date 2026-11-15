import asyncio
import json
from pathlib import Path

import pytest

from app.domain.run_state import RunState
from app.services.developer_monitor import snapshot
from app.services.device_classification import classify_computer_name
from app.services.device_presence import DevicePresence
from app.services.session_audit import SessionAudit

CASES = json.loads((Path(__file__).parent / "fixtures/device-naming-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_computer_names_classify_only_known_tokens(case):
    value = classify_computer_name(case["name"])
    for field in ("sector", "station_type", "branch"):
        assert (value[field]["code"] if value[field] else None) == case[field]
    assert value["conflicts"] == case.get("conflicts", [])
    assert value["rules_version"] == 1 and value["source"] == "computer_name"


def test_old_shared_clients_and_sessions_are_classified_without_a_schema_migration(tmp_path):
    identity = lambda: {"computer_name": "WKS-COMP-VIN-01", "windows_user": "DOMAIN\\actor", "mac_addresses": []}
    audit = SessionAudit(tmp_path / "local.sqlite", tmp_path / "shared.sqlite", identity)
    session = audit.login("Operador", {"status": "idle"})
    assert session["classification"]["sector"] == {"code": "COMP", "label": "Compras"}
    audit.sync()
    legacy = snapshot(audit)["devices"][0]
    assert legacy["installation_kind"] == "unreported"
    assert legacy["classification"]["sector"]["code"] == "COMP"
    asyncio.run(DevicePresence(audit, tmp_path, RunState()).tick())
    audit.sync()
    view = snapshot(audit)
    assert view["devices"][0]["classification"]["station_type"]["code"] == "WKS"
    assert view["sessions"][0]["classification"]["branch"]["code"] == "VIN"
    assert view["devices"][0]["automation_status"] == "stopped"


def test_unknown_sector_does_not_prevent_login_or_change_automation_permissions(tmp_path):
    audit = SessionAudit(tmp_path / "local.sqlite", tmp_path / "shared.sqlite",
                         lambda: {"computer_name": "CUSTOM-PC", "windows_user": "D\\user", "mac_addresses": []})
    session = audit.login("Operador", {"status": "idle"})
    assert session["status"] == "active" and session["classification"]["sector"] is None
