"""Coordinate the single save attempt through the existing shared SQLite store."""

import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.pending_queue import cte_number, identity
from app.infrastructure.sqlite_lease import WriterLease


class Submissions:
    def __init__(self, cwd, config):
        self.root = cwd / "runtime/novelis-http/submissions"
        path = config.get("chamadoSubmissionDb")
        self.store = OperationsStore(Path(path)) if path else None
        self.cwd = cwd

    def _key(self, row):
        return "novelis-http:" + hashlib.sha256(identity(row).encode()).hexdigest()

    @contextmanager
    def _local_file(self, row):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / (self._key(row).split(":")[1] + ".json")
        lease = WriterLease(path)
        lease.acquire()
        try:
            yield path
        finally:
            lease.close()

    def reserve(self, row, run_id):
        old = self.cwd / "runtime/chamado-http-tests" / f"submission-{cte_number(row)}.json"
        if old.is_file():
            return json.loads(old.read_text(encoding="utf-8"))
        value = {
            "status": "submitting",
            "cte": cte_number(row),
            "run_id": run_id,
            "submitted": True,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if self.store:
            with self.store.connection() as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS app_snapshots (name TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)"
                )
                inserted = db.execute(
                    "INSERT OR IGNORE INTO app_snapshots VALUES (?,?,?)",
                    (self._key(row), json.dumps(value), value["updated_at"]),
                ).rowcount
                return (
                    None
                    if inserted
                    else json.loads(
                        db.execute(
                            "SELECT payload FROM app_snapshots WHERE name=?", (self._key(row),)
                        ).fetchone()[0]
                    )
                )
        with self._local_file(row) as path:
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
            with path.open("x", encoding="utf-8") as stream:
                json.dump(value, stream)
        return None

    def finish(self, row, value):
        value = {**value, "updated_at": datetime.now(UTC).isoformat()}
        if self.store:
            with self.store.connection() as db:
                previous = db.execute(
                    "SELECT payload FROM app_snapshots WHERE name=?", (self._key(row),)
                ).fetchone()
                if (
                    previous
                    and json.loads(previous[0]).get("status") == "confirmed"
                    and value["status"] != "confirmed"
                ):
                    return
                db.execute(
                    "INSERT INTO app_snapshots VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
                    (self._key(row), json.dumps(value, ensure_ascii=False), value["updated_at"]),
                )
        else:
            with self._local_file(row) as path:
                previous = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
                if previous.get("status") == "confirmed" and value["status"] != "confirmed":
                    return
                temporary = path.with_suffix(".tmp")
                temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                temporary.replace(path)

    def release(self, row, run_id):
        if self.store:
            with self.store.connection() as db:
                db.execute(
                    "DELETE FROM app_snapshots WHERE name=? AND json_extract(payload,'$.run_id')=? AND json_extract(payload,'$.status')='submitting'",
                    (self._key(row), run_id),
                )
        else:
            with self._local_file(row) as path:
                if path.is_file():
                    value = json.loads(path.read_text(encoding="utf-8"))
                    if value.get("run_id") == run_id and value.get("status") == "submitting":
                        path.unlink()
