"""Private developer view of detected installations and operator sessions."""
import hashlib
import json
from datetime import UTC, datetime

from app.infrastructure.session_audit_db import connection

ONLINE_TIMEOUT_SECONDS = 90


def recent(timestamp: str, now: datetime) -> bool:
    try:
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            return False
        return -15 <= (now - parsed).total_seconds() <= ONLINE_TIMEOUT_SECONDS
    except (ValueError, TypeError):
        return False


def addresses(value):
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []


def snapshot(audit, now=None) -> dict:
    now = now or datetime.now(UTC)
    with connection(audit.shared_path) as db:
        devices = [dict(row) for row in db.execute("SELECT * FROM devices ORDER BY last_seen_at DESC LIMIT 1001")]
        sessions = [dict(row) for row in db.execute("SELECT * FROM sessions ORDER BY last_seen_at DESC LIMIT 501")]
    truncated = len(devices) > 1000 or len(sessions) > 500
    devices, sessions = devices[:1000], sessions[:500]
    for device in devices:
        device["mac_addresses"] = addresses(device["mac_addresses"])
        device["online"] = device["backend_status"] == "online" and recent(device["last_seen_at"], now)
        device["operators"] = []
        # The backend instance identifier is internal, not an operator credential.
        device.pop("instance_id", None)
    by_machine = {}
    for device in devices:
        by_machine.setdefault(device["machine_id"], []).append(device)
    for session in sessions:
        session["id"] = hashlib.sha256(session["id"].encode()).hexdigest()[:24]
        session["mac_addresses"] = addresses(session["mac_addresses"])
        clients = by_machine.get(session["machine_id"], [])
        online = any(value["online"] for value in clients) if clients else recent(session["last_seen_at"], now)
        session["online"] = session["status"] == "active" and online and recent(session["last_seen_at"], now)
        session["display_status"] = "stale" if session["status"] == "active" and not session["online"] else session["status"]
        if session["online"]:
            for device in clients:
                if device["online"] and session["operator_name"] not in device["operators"]:
                    device["operators"].append(session["operator_name"])
    # Existing clients with only login records remain visible, with installation unconfirmed.
    legacy = {}
    for session in sessions:
        if session["machine_id"] not in by_machine and session["machine_id"] not in legacy:
            legacy[session["machine_id"]] = {"id": "legacy:" + session["machine_id"],
                "machine_id": session["machine_id"], "computer_name": session["computer_name"],
                "windows_user": session["windows_user"], "mac_addresses": session["mac_addresses"],
                "version": None, "installation_kind": "unreported", "install_root": None,
                "first_seen_at": None, "last_seen_at": session["last_seen_at"], "backend_started_at": None,
                "backend_status": "unreported", "automation_status": session["automation_status"],
                "run_id": session["run_id"], "updated_at": session["updated_at"], "online": session["online"],
                "operators": []}
        if session["online"] and session["machine_id"] in legacy:
            legacy[session["machine_id"]]["online"] = True
            legacy[session["machine_id"]]["automation_status"] = session["automation_status"]
            names = legacy[session["machine_id"]]["operators"]
            if session["operator_name"] not in names:
                names.append(session["operator_name"])
    devices.extend(legacy.values())
    devices.sort(key=lambda item: (item["online"], item["last_seen_at"]), reverse=True)
    truncated = truncated or len(devices) > 1000
    devices = devices[:1000]
    sessions.sort(key=lambda item: (item["online"], item["last_seen_at"]), reverse=True)
    online = [item for item in devices if item["online"]]
    return {"checked_at": now.isoformat(), "online_timeout_seconds": ONLINE_TIMEOUT_SECONDS,
            "source": "shared_session_audit", "truncated": truncated,
            "local_pending_sync": audit.pending(), "devices": devices, "sessions": sessions,
            "summary": {"detected_installations": sum(item["installation_kind"] == "installed" for item in devices),
                "online_devices": len({item["machine_id"] for item in online}),
                "logged_in_users": len({item["windows_user"].casefold() for item in sessions if item["online"]}),
                "running_automations": len({item["machine_id"] for item in online if item["automation_status"] in {"running", "stopping"}}),
                "broken_automations": len({item["machine_id"] for item in online if item["automation_status"] == "broken"})}}
