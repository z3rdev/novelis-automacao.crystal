"""Coordinated SQLite transactions for local audit and shared replication."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.infrastructure.sqlite_lease import WriterLease

SESSION_COLUMNS = ("id", "machine_id", "operator_name", "windows_user", "computer_name", "mac_addresses",
                   "login_at", "last_seen_at", "logout_at", "status", "automation_status", "run_id", "updated_at")
EVENT_COLUMNS = ("id", "session_id", "run_id", "machine_id", "windows_user", "status", "recorded_at")


@contextmanager
def connection(path: Path, *, local: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    lease = WriterLease(path)
    lease.acquire()
    db = None
    try:
        db = sqlite3.connect(path, timeout=10)
        with db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA journal_mode=DELETE")
            if db.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise RuntimeError("Versao do banco de auditoria mais recente que este backend.")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, machine_id TEXT NOT NULL, operator_name TEXT NOT NULL,
                    windows_user TEXT NOT NULL, computer_name TEXT NOT NULL, mac_addresses TEXT NOT NULL,
                    login_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, logout_at TEXT,
                    status TEXT NOT NULL, automation_status TEXT NOT NULL, run_id TEXT, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ix_sessions_machine ON sessions(machine_id, login_at);
                CREATE TABLE IF NOT EXISTS automation_events (
                    id TEXT PRIMARY KEY, session_id TEXT, run_id TEXT NOT NULL, machine_id TEXT NOT NULL,
                    windows_user TEXT NOT NULL, status TEXT NOT NULL, recorded_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS ix_audit_run ON automation_events(run_id, recorded_at);
                PRAGMA user_version=1;
            """)
            if local:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS audit_runs (run_id TEXT PRIMARY KEY, session_id TEXT, status TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS sync_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL);
                """)
            with db:
                yield db
    finally:
        try:
            if db is not None:
                db.close()
        finally:
            lease.close()


def apply(db, payload: dict) -> None:
    columns = ",".join(SESSION_COLUMNS)
    updates = ",".join(f"{column}=excluded.{column}" for column in SESSION_COLUMNS if column != "id")
    for session in payload.get("sessions", []):
        db.execute(f"INSERT INTO sessions ({columns}) VALUES ({','.join('?' for _ in SESSION_COLUMNS)}) "
                   f"ON CONFLICT(id) DO UPDATE SET {updates} WHERE excluded.updated_at >= sessions.updated_at",
                   tuple(session.get(column) for column in SESSION_COLUMNS))
    event = payload.get("event")
    if event:
        db.execute(f"INSERT OR IGNORE INTO automation_events ({','.join(EVENT_COLUMNS)}) "
                   f"VALUES ({','.join('?' for _ in EVENT_COLUMNS)})", tuple(event.get(column) for column in EVENT_COLUMNS))


def enqueue(db, payload: dict) -> None:
    apply(db, payload)
    db.execute("INSERT INTO sync_queue(payload) VALUES (?)", (json.dumps(payload, ensure_ascii=False),))
