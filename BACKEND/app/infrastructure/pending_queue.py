"""Shared unopened CT-es, independent of an individual run's document plan."""
import hashlib
import json
import re
from datetime import UTC, datetime
from app.domain.cte_authorization import authorization_status

SCHEMA = """
CREATE TABLE IF NOT EXISTS hub_pending_ctes (
    identity TEXT PRIMARY KEY, cte TEXT NOT NULL, row_json TEXT NOT NULL,
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending', closed_at TEXT);
CREATE INDEX IF NOT EXISTS ix_hub_pending_state ON hub_pending_ctes(state);
CREATE TABLE IF NOT EXISTS hub_pending_sources (
    source TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
"""


def access_key(row):
    digits = re.sub(r"\D", "", str(row.get("cteId") or row.get("CTE_ID") or row.get("chave") or ""))
    return digits if len(digits) == 44 else ""


def cte_number(row):
    parts = [str(row.get(key) or row.get(key.upper()) or "") for key in ("filial", "serie", "documento")]
    if not all(parts):
        parts = str(row.get("cte") or "").split("-")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return ""
    return "-".join(str(int(part)) for part in parts)


def identity(row):
    return access_key(row) or cte_number(row)


def stamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=result.tzinfo or UTC).astimezone(UTC).isoformat()
    except (ValueError, TypeError):
        return datetime.now(UTC).isoformat()


class PendingQueue:
    def __init__(self, store):
        self.store = store

    def ingest(self, payload, source):
        rows = [item.get("row", {}) for item in payload.get("checked", [])] if "checked" in payload else payload.get("rows", [])
        rows = [row for row in rows if isinstance(row, dict) and cte_number(row)]
        fingerprint = hashlib.sha256(json.dumps(["authorization-v1", payload.get("generatedAt"), rows], sort_keys=True, default=str).encode()).hexdigest()
        timestamp = stamp(payload.get("generatedAt"))
        with self.store.connection() as db:
            db.executescript(SCHEMA)
            previous = db.execute("SELECT fingerprint FROM hub_pending_sources WHERE source=?", (source,)).fetchone()
            if previous and previous[0] == fingerprint:
                return 0
            for row in rows:
                authorization = authorization_status(row)
                if authorization == "N":
                    db.execute("UPDATE hub_pending_ctes SET state='unauthorized',last_seen=? "
                               "WHERE cte=? AND state<>'opened' AND last_seen<=?",
                               (timestamp, cte_number(row), timestamp))
                elif not authorization:
                    previous_rows = db.execute(
                        "SELECT state,row_json FROM hub_pending_ctes WHERE cte=? AND state<>'opened'",
                        (cte_number(row),)).fetchall()
                    if any(value[0] == "unauthorized" or authorization_status(json.loads(value[1])) == "N" for value in previous_rows):
                        continue
                if access_key(row):
                    db.execute("DELETE FROM hub_pending_ctes WHERE identity=? AND state='pending'", (cte_number(row),))
                elif authorization != "N" and db.execute("SELECT 1 FROM hub_pending_ctes WHERE cte=? AND length(identity)=44 AND state='pending'", (cte_number(row),)).fetchone():
                    continue
                state = "unauthorized" if authorization == "N" else "pending"
                db.execute("INSERT INTO hub_pending_ctes(identity,cte,row_json,first_seen,last_seen,state) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(identity) DO UPDATE SET row_json=excluded.row_json,last_seen=excluded.last_seen,state=excluded.state "
                    "WHERE hub_pending_ctes.state<>'opened' AND hub_pending_ctes.last_seen<=excluded.last_seen "
                    "AND (hub_pending_ctes.state<>'unauthorized' OR ? IN ('S','N'))",
                    (identity(row), cte_number(row), json.dumps(row, ensure_ascii=False, default=str), timestamp, timestamp, state, authorization))
            db.execute("INSERT INTO hub_pending_sources VALUES (?,?) ON CONFLICT(source) DO UPDATE SET fingerprint=excluded.fingerprint",
                       (source, fingerprint))
        return len(rows)

    def rows(self):
        with self.store.connection() as db:
            db.executescript(SCHEMA)
            rows = db.execute("SELECT row_json FROM hub_pending_ctes WHERE state='pending' ORDER BY first_seen,cte").fetchall()
        values = [json.loads(row[0]) for row in rows]
        return [row for row in values if authorization_status(row) != "N"]

    def close(self, identities):
        if not identities:
            return
        with self.store.connection() as db:
            db.executemany("UPDATE hub_pending_ctes SET state='opened',closed_at=? WHERE identity=? AND state='pending'",
                           [(datetime.now(UTC).isoformat(), key) for key in identities])

    def last_seen(self):
        with self.store.connection() as db:
            db.executescript(SCHEMA)
            return db.execute("SELECT max(last_seen) FROM hub_pending_ctes").fetchone()[0]
