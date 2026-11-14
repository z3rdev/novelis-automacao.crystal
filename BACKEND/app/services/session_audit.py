"""Durable operator sessions and automation states replicated to the requested share."""
import asyncio
import json
import logging
import sqlite3
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

from app.infrastructure.session_audit_db import apply, connection, enqueue
from app.services.device_identity import device_identity

operator_session = ContextVar("operator_session", default=None)
STATES = {"idle": "stopped", "running": "running", "stopping": "stopping", "completed": "completed",
          "failed": "broken", "cancelled": "cancelled"}
logger = logging.getLogger(__name__)


def now() -> str:
    return datetime.now(UTC).isoformat()


class SessionAudit:
    def __init__(self, local_path: Path, shared_path: Path, identity=device_identity):
        self.local_path, self.shared_path, self.identity = local_path, shared_path, identity
        self._lock = RLock()
        self._sync_lock = RLock()
        self.sync_error = False

    def login(self, name: str, snapshot: dict) -> dict:
        identity, timestamp = self.identity(), now()
        session = {"id": str(uuid4()), "machine_id": identity["computer_name"].casefold(),
                   "operator_name": name, **identity, "mac_addresses": json.dumps(identity["mac_addresses"]),
                   "login_at": timestamp, "last_seen_at": timestamp, "logout_at": None,
                   "status": "active", "automation_status": STATES[snapshot["status"]],
                   "run_id": snapshot.get("id"), "updated_at": timestamp}
        with self._lock, connection(self.local_path, local=True) as db:
            enqueue(db, {"sessions": [session]})
        return self.session(session["id"])

    def session(self, identifier: str, *, touch: bool = False) -> dict | None:
        with self._lock, connection(self.local_path, local=True) as db:
            row = db.execute("SELECT * FROM sessions WHERE id=? AND status='active'", (identifier,)).fetchone()
            if not row or row["windows_user"] != self.identity()["windows_user"]:
                return None
            value = dict(row)
            if touch:
                value.update(last_seen_at=now(), updated_at=now())
                enqueue(db, {"sessions": [value]})
            value["mac_addresses"] = json.loads(value["mac_addresses"])
            return value

    def logout(self, identifier: str) -> None:
        with self._lock, connection(self.local_path, local=True) as db:
            row = db.execute("SELECT * FROM sessions WHERE id=? AND status='active'", (identifier,)).fetchone()
            if row and row["windows_user"] == self.identity()["windows_user"]:
                value = {**dict(row), "status": "logged_out", "logout_at": now(), "updated_at": now()}
                enqueue(db, {"sessions": [value]})

    def recover(self) -> None:
        with self._lock, connection(self.local_path, local=True) as db:
            for row in db.execute("SELECT * FROM sessions WHERE status='active'").fetchall():
                enqueue(db, {"sessions": [{**dict(row), "status": "interrupted", "logout_at": now(), "updated_at": now()}]})

    def record_run(self, snapshot: dict, session_id: str | None) -> None:
        identity, timestamp = self.identity(), now()
        status = STATES[snapshot["status"]]
        with self._lock, connection(self.local_path, local=True) as db:
            existing = db.execute("SELECT * FROM audit_runs WHERE run_id=?", (snapshot["id"],)).fetchone()
            if existing and existing["status"] == status:
                return
            owner = existing["session_id"] if existing else session_id
            db.execute("INSERT INTO audit_runs VALUES (?,?,?) ON CONFLICT(run_id) DO UPDATE SET status=excluded.status",
                       (snapshot["id"], owner, status))
            sessions = [{**dict(row), "automation_status": status, "run_id": snapshot["id"], "updated_at": timestamp}
                        for row in db.execute("SELECT * FROM sessions WHERE status='active' OR id=?", (owner,)).fetchall()]
            event = {"id": str(uuid4()), "session_id": owner, "run_id": snapshot["id"],
                     "machine_id": identity["computer_name"].casefold(), "windows_user": identity["windows_user"],
                     "status": status, "recorded_at": timestamp}
            enqueue(db, {"sessions": sessions, "event": event})

    def pending(self) -> int:
        with self._lock, connection(self.local_path, local=True) as db:
            return db.execute("SELECT COUNT(*) FROM sync_queue").fetchone()[0]

    def heartbeat(self, device: dict, snapshot: dict) -> None:
        timestamp = device["last_seen_at"]
        stopped = device["backend_status"] == "stopped"
        with self._lock, connection(self.local_path, local=True) as db:
            current = db.execute("SELECT instance_id FROM devices WHERE id=?", (device["id"],)).fetchone()
            if stopped and current and current["instance_id"] != device["instance_id"]:
                return
            sessions = []
            for row in db.execute("SELECT * FROM sessions WHERE status='active'").fetchall():
                value = {**dict(row), "last_seen_at": timestamp, "updated_at": timestamp,
                         "automation_status": STATES[snapshot["status"]], "run_id": snapshot.get("id")}
                if stopped:
                    value.update(status="interrupted", logout_at=timestamp)
                sessions.append(value)
            # Keep the latest periodic signal during an outage; retain login/logout/run events.
            db.execute("DELETE FROM sync_queue WHERE json_extract(payload,'$.heartbeat')=1 "
                       "AND json_extract(payload,'$.device.id')=?", (device["id"],))
            enqueue(db, {"heartbeat": not stopped, "device": device, "sessions": sessions})

    def sync(self) -> int:
        with self._sync_lock:
            with self._lock, connection(self.local_path, local=True) as db:
                rows = db.execute("SELECT id,payload FROM sync_queue ORDER BY id LIMIT 100").fetchall()
            if not rows:
                return 0
            with connection(self.shared_path) as shared:
                for row in rows:
                    apply(shared, json.loads(row["payload"]))
            with self._lock, connection(self.local_path, local=True) as db:
                db.executemany("DELETE FROM sync_queue WHERE id=?", [(row["id"],) for row in rows])
            return len(rows)

    async def sync_loop(self):
        while True:
            try:
                await asyncio.to_thread(self.sync)
                self.sync_error = False
            except (OSError, sqlite3.Error, RuntimeError):
                self.sync_error = True
                logger.warning("Logs de sessao preservados localmente, aguardando sincronizacao com o compartilhamento.")
            await asyncio.sleep(15)
