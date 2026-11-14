from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.hub_features import ScheduleInput


class ScheduleRepository:
    def __init__(self, store):
        self.store = store

    def list(self, windows_user: str) -> list[dict]:
        with self.store.connection() as db:
            rows = db.execute("SELECT id,payload,revision,activated_at FROM hub_schedules WHERE machine_id=? "
                              "AND windows_user=? AND deleted_at IS NULL ORDER BY json_extract(payload,'$.time'),id",
                              (self.store.machine_id, windows_user.casefold())).fetchall()
            result = []
            for identifier, payload, revision, activated_at in rows:
                value = {**json.loads(payload), "id": identifier, "revision": revision, "activated_at": activated_at}
                cursor = db.execute("SELECT local_date,state,run_id,started_at,finished_at,message FROM hub_schedule_occurrences "
                                    "WHERE schedule_id=? ORDER BY local_date DESC LIMIT 1", (identifier,))
                occurrence = cursor.fetchone()
                value["last_run"] = dict(zip([column[0] for column in cursor.description], occurrence)) if occurrence else None
                result.append(value)
            return result

    def save(self, body: ScheduleInput, actor: dict, now: datetime, identifier: str | None = None) -> str:
        timestamp = now.astimezone(UTC).isoformat()
        payload = {**body.model_dump(mode="json"), "operator_name": actor["operator_name"]}
        with self.store.connection() as db:
            if identifier:
                previous = db.execute("SELECT payload,activated_at FROM hub_schedules WHERE id=? AND machine_id=? AND windows_user=? AND deleted_at IS NULL",
                    (identifier, self.store.machine_id, actor["windows_user"].casefold())).fetchone()
                if not previous:
                    raise KeyError(identifier)
                old = json.loads(previous[0])
                activated = previous[1] if all(old.get(key) == payload[key] for key in ("time", "weekdays", "flow", "days_back", "enabled")) else timestamp
                db.execute("UPDATE hub_schedules SET payload=?,revision=revision+1,activated_at=?,updated_at=? WHERE id=?",
                    (json.dumps(payload, ensure_ascii=False), activated, timestamp, identifier))
            else:
                identifier = str(uuid4())
                db.execute("INSERT INTO hub_schedules VALUES (?,?,?,?,?,?,?,NULL)",
                    (identifier, self.store.machine_id, actor["windows_user"].casefold(), json.dumps(payload, ensure_ascii=False), 1, timestamp, timestamp))
        return identifier

    def remove(self, identifier: str, windows_user: str) -> bool:
        with self.store.connection() as db:
            return bool(db.execute("UPDATE hub_schedules SET deleted_at=?,revision=revision+1 WHERE id=? AND machine_id=? AND windows_user=? AND deleted_at IS NULL",
                (datetime.now(UTC).isoformat(), identifier, self.store.machine_id, windows_user.casefold())).rowcount)

    def claim(self, value: dict, local_date: str, now: datetime) -> bool:
        with self.store.connection() as db:
            row = db.execute("SELECT payload,revision FROM hub_schedules WHERE id=? AND deleted_at IS NULL", (value["id"],)).fetchone()
            if not row or row[1] != value["revision"] or not json.loads(row[0])["enabled"]:
                return False
            return bool(db.execute("INSERT OR IGNORE INTO hub_schedule_occurrences VALUES (?,?,?,NULL,NULL,?,NULL,?,?)",
                (value["id"], local_date, "starting", now.astimezone(UTC).isoformat(), "Preparando execução agendada.", json.dumps(value, ensure_ascii=False))).rowcount)

    def release_claim(self, identifier: str, local_date: str) -> None:
        with self.store.connection() as db:
            db.execute("DELETE FROM hub_schedule_occurrences WHERE schedule_id=? AND local_date=? AND state='starting' AND run_id IS NULL", (identifier, local_date))

    def update(self, identifier: str, local_date: str, state: str, message: str, *, run_id=None, session_id=None, finished=False) -> None:
        with self.store.connection() as db:
            db.execute("UPDATE hub_schedule_occurrences SET state=?,message=?,run_id=COALESCE(?,run_id),session_id=COALESCE(?,session_id),finished_at=? WHERE schedule_id=? AND local_date=?",
                (state, message, run_id, session_id, datetime.now(UTC).isoformat() if finished else None, identifier, local_date))

    def active(self, windows_user: str) -> list[dict]:
        with self.store.connection() as db:
            cursor = db.execute("SELECT o.* FROM hub_schedule_occurrences o JOIN hub_schedules s ON s.id=o.schedule_id "
                                "WHERE s.machine_id=? AND s.windows_user=? AND o.state IN ('starting','running')",
                                (self.store.machine_id, windows_user.casefold()))
            keys = [column[0] for column in cursor.description]
            return [dict(zip(keys, row)) for row in cursor.fetchall()]
