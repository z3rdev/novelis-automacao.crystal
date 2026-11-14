"""Shared SQLite accessed by local backends, with short serialized transactions."""

import json
import socket
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock

from app.infrastructure.sqlite_lease import WriterLease
from app.infrastructure.hub_features_schema import FEATURE_SCHEMA


class OperationsStore:
    def __init__(self, path: Path, machine_id: str | None = None):
        self.path = path
        self.machine_id = machine_id or socket.gethostname().casefold()
        self._lock = RLock()
        self.ready = False

    def initialize(self) -> None:
        if not self.path.parent.is_dir():
            raise RuntimeError("Pasta do SQLite indisponivel. Verifique o compartilhamento configurado.")
        with self._connection() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise RuntimeError("Versao do banco mais recente que este backend.")
            db.execute("PRAGMA journal_mode=DELETE")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS app_snapshots (
                    name TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS execution_runs (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS execution_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ix_events_run ON execution_events(run_id, id);
                CREATE TABLE IF NOT EXISTS app_preferences (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL);
                PRAGMA user_version=1;
            """)
            db.executescript(FEATURE_SCHEMA)
        self.ready = True

    @contextmanager
    def connection(self):
        with self._lock:
            lease = WriterLease(self.path)
            lease.acquire()
            db = None
            try:
                db = sqlite3.connect(str(self.path), timeout=10)
                db.execute("PRAGMA busy_timeout=10000")
                db.execute("PRAGMA synchronous=FULL")
                db.execute("PRAGMA foreign_keys=ON")
                with db:
                    yield db
            finally:
                try:
                    if db is not None:
                        db.close()
                finally:
                    lease.close()

    _connection = connection

    def run_by_id(self, run_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT payload FROM execution_runs WHERE id=?", (run_id,)).fetchone()
        value = json.loads(row[0]) if row else None
        return value if value and value.get("machine_id") == self.machine_id else None

    def close(self) -> None:
        with self._lock:
            self.ready = False

    def local_snapshot(self, name: str, payload=None):
        return self.snapshot(f"{self.machine_id}:{name}", payload)

    def snapshot(self, name: str, payload=None):
        with self._connection() as db:
            if payload is None:
                row = db.execute("SELECT payload FROM app_snapshots WHERE name=?", (name,)).fetchone()
                return json.loads(row[0]) if row else None
            encoded = json.dumps(payload, ensure_ascii=False)
            row = db.execute("SELECT payload FROM app_snapshots WHERE name=?", (name,)).fetchone()
            if not row or row[0] != encoded:
                db.execute(
                    "INSERT INTO app_snapshots VALUES (?,?,?) ON CONFLICT(name) "
                    "DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                    (name, encoded, datetime.now(UTC).isoformat()),
                )
        return payload

    def save_run(self, payload: dict) -> None:
        payload = {**payload, "machine_id": self.machine_id}
        with self._connection() as db:
            db.execute(
                "INSERT INTO execution_runs VALUES (?,?,?) ON CONFLICT(id) "
                "DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (payload["id"], json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )

    def last_run(self) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT payload FROM execution_runs WHERE json_extract(payload,'$.machine_id')=? "
                             "ORDER BY updated_at DESC LIMIT 1", (self.machine_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def add_event(self, payload: dict) -> int:
        payload = {**payload, "machine_id": self.machine_id}
        with self._connection() as db:
            cursor = db.execute(
                "INSERT INTO execution_events(run_id,payload) VALUES (?,?)",
                (payload.get("run_id"), json.dumps(payload, ensure_ascii=False)),
            )
            return int(cursor.lastrowid)

    def events(self, run_id: str | None = None, limit: int = 300, *, all_machines: bool = False) -> list[dict]:
        with self._connection() as db:
            sql = "SELECT id,payload FROM execution_events WHERE 1=1"
            params = []
            if not all_machines:
                sql += " AND json_extract(payload,'$.machine_id')=?"
                params.append(self.machine_id)
            if run_id:
                sql += " AND run_id=?"
                params.append(run_id)
            rows = db.execute(sql + " ORDER BY id DESC LIMIT ?", (*params, min(limit, 1000))).fetchall()
        return [{**json.loads(value), "id": key} for key, value in reversed(rows)]

    def preferences(self, values: dict | None = None) -> dict:
        prefix = f"{self.machine_id}:"
        with self._connection() as db:
            if values:
                db.executemany(
                    "INSERT INTO app_preferences VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                    [(prefix + key, str(value)) for key, value in values.items()],
                )
            rows = db.execute("SELECT name,value FROM app_preferences WHERE substr(name,1,?)=?",
                              (len(prefix), prefix)).fetchall()
            return {key[len(prefix):]: value for key, value in rows}

    def health(self) -> dict:
        with self._connection() as db:
            return {"path": str(self.path), "ready": self.ready,
                    "machine_id": self.machine_id,
                    "journal_mode": db.execute("PRAGMA journal_mode").fetchone()[0],
                    "schema_version": db.execute("PRAGMA user_version").fetchone()[0],
                    "runs": db.execute("SELECT COUNT(*) FROM execution_runs").fetchone()[0],
                    "events": db.execute("SELECT COUNT(*) FROM execution_events").fetchone()[0]}
