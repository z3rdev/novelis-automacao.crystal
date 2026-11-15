from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.hub_features import ScheduleInput


def records(cursor):
    keys = [column[0] for column in cursor.description]
    return [dict(zip(keys, row)) for row in cursor.fetchall()]


class ScheduleRepository:
    def __init__(self, store):
        self.store = store

    def list(self, windows_user: str) -> list[dict]:
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT id,payload,revision,activated_at FROM hub_schedules WHERE machine_id=? "
                "AND windows_user=? AND deleted_at IS NULL ORDER BY json_extract(payload,'$.time'),id",
                (self.store.machine_id, windows_user.casefold()),
            ).fetchall()
            result = []
            for identifier, payload, revision, activated_at in rows:
                stored = json.loads(payload)
                value = {
                    **stored,
                    **ScheduleInput.model_validate(stored).model_dump(mode="json"),
                    "id": identifier,
                    "revision": revision,
                    "activated_at": activated_at,
                }
                history = records(
                    db.execute(
                        "SELECT local_date,slot,attempt,due_at,state,run_id,started_at,finished_at,message "
                        "FROM hub_schedule_attempts WHERE schedule_id=? AND (state IN ('waiting','starting','running') "
                        "OR local_date>=date((SELECT max(local_date) FROM hub_schedule_attempts WHERE schedule_id=?),'-1 day')) "
                        "ORDER BY local_date DESC,slot DESC,attempt DESC",
                        (identifier, identifier),
                    )
                )
                value["occurrences"] = history
                value["last_run"] = max(
                    (row for row in history if row.get("started_at")),
                    key=lambda row: datetime.fromisoformat(row["started_at"]),
                    default=None,
                )
                result.append(value)
            return result

    def save(
        self, body: ScheduleInput, actor: dict, now: datetime, identifier: str | None = None
    ) -> str:
        timestamp = now.astimezone(UTC).isoformat()
        payload = {**body.model_dump(mode="json"), "operator_name": actor["operator_name"]}
        with self.store.connection() as db:
            if identifier:
                previous = db.execute(
                    "SELECT payload,activated_at FROM hub_schedules WHERE id=? AND machine_id=? "
                    "AND windows_user=? AND deleted_at IS NULL",
                    (identifier, self.store.machine_id, actor["windows_user"].casefold()),
                ).fetchone()
                if not previous:
                    raise KeyError(identifier)
                old = ScheduleInput.model_validate_json(previous[0]).model_dump(mode="json")
                keys = set(ScheduleInput.model_fields) - {"name"}
                activated = (
                    previous[1] if all(old[key] == payload[key] for key in keys) else timestamp
                )
                db.execute(
                    "UPDATE hub_schedules SET payload=?,revision=revision+1,activated_at=?,updated_at=? WHERE id=?",
                    (json.dumps(payload, ensure_ascii=False), activated, timestamp, identifier),
                )
                db.execute(
                    "UPDATE hub_schedule_attempts SET state='cancelled',finished_at=?,message=? "
                    "WHERE schedule_id=? AND state='waiting'",
                    (timestamp, "Configuração alterada antes da nova tentativa.", identifier),
                )
            else:
                identifier = str(uuid4())
                db.execute(
                    "INSERT INTO hub_schedules VALUES (?,?,?,?,?,?,?,NULL)",
                    (
                        identifier,
                        self.store.machine_id,
                        actor["windows_user"].casefold(),
                        json.dumps(payload, ensure_ascii=False),
                        1,
                        timestamp,
                        timestamp,
                    ),
                )
        return identifier

    def remove(self, identifier: str, windows_user: str) -> bool:
        with self.store.connection() as db:
            changed = db.execute(
                "UPDATE hub_schedules SET deleted_at=?,revision=revision+1 WHERE id=? AND machine_id=? "
                "AND windows_user=? AND deleted_at IS NULL",
                (
                    datetime.now(UTC).isoformat(),
                    identifier,
                    self.store.machine_id,
                    windows_user.casefold(),
                ),
            ).rowcount
            if changed:
                db.execute(
                    "UPDATE hub_schedule_attempts SET state='cancelled',message='Agendamento removido.' "
                    "WHERE schedule_id=? AND state='waiting'",
                    (identifier,),
                )
            return bool(changed)

    def claim(self, value, local_date, now, *, slot=0, attempt=0, due_at=None):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT payload,revision FROM hub_schedules WHERE id=? AND machine_id=? AND deleted_at IS NULL",
                (value["id"], self.store.machine_id),
            ).fetchone()
            if not row or row[1] != value["revision"] or not json.loads(row[0])["enabled"]:
                return False
            if db.execute(
                "SELECT 1 FROM hub_schedule_attempts o JOIN hub_schedules s ON s.id=o.schedule_id "
                "WHERE s.machine_id=? AND o.state IN ('starting','running') LIMIT 1",
                (self.store.machine_id,),
            ).fetchone():
                return False
            timestamp = now.astimezone(UTC).isoformat()
            if attempt:
                return bool(
                    db.execute(
                        "UPDATE hub_schedule_attempts SET state='starting',started_at=? WHERE schedule_id=? "
                        "AND local_date=? AND slot=? AND attempt=? AND state='waiting' AND due_at<=?",
                        (timestamp, value["id"], local_date, slot, attempt, timestamp),
                    ).rowcount
                )
            settings = {key: value[key] for key in ScheduleInput.model_fields}
            settings.update(revision=value["revision"], operator_name=value["operator_name"])
            return bool(
                db.execute(
                    "INSERT OR IGNORE INTO hub_schedule_attempts VALUES (?,?,?,?,?,'starting',NULL,NULL,?,NULL,?,?)",
                    (
                        value["id"],
                        local_date,
                        slot,
                        0,
                        (due_at or now).astimezone(UTC).isoformat(),
                        timestamp,
                        "Preparando execução agendada.",
                        json.dumps(settings, ensure_ascii=False),
                    ),
                ).rowcount
            )

    def release_claim(self, identifier, local_date, *, slot=0, attempt=0):
        with self.store.connection() as db:
            key = (identifier, local_date, slot, attempt)
            if attempt:
                db.execute(
                    "UPDATE hub_schedule_attempts SET state='waiting',started_at=NULL "
                    "WHERE schedule_id=? AND local_date=? AND slot=? AND attempt=? "
                    "AND state='starting' AND run_id IS NULL",
                    key,
                )
            else:
                db.execute(
                    "DELETE FROM hub_schedule_attempts WHERE schedule_id=? AND local_date=? "
                    "AND slot=? AND attempt=? AND state='starting' AND run_id IS NULL",
                    key,
                )

    def update(
        self,
        identifier,
        local_date,
        state,
        message,
        *,
        run_id=None,
        session_id=None,
        finished=False,
        slot=0,
        attempt=0,
        now=None,
    ):
        now = now or datetime.now(UTC)
        timestamp = now.astimezone(UTC).isoformat()
        with self.store.connection() as db:
            db.execute(
                "UPDATE hub_schedule_attempts SET state=?,message=?,run_id=COALESCE(?,run_id),"
                "session_id=COALESCE(?,session_id),finished_at=? WHERE schedule_id=? AND local_date=? AND slot=? AND attempt=?",
                (
                    state,
                    message,
                    run_id,
                    session_id,
                    timestamp if finished else None,
                    identifier,
                    local_date,
                    slot,
                    attempt,
                ),
            )
            if finished and state == "failed":
                return self._retry(db, identifier, local_date, slot, attempt, now)
        return False

    def _retry(self, db, identifier, local_date, slot, attempt, now):
        row = db.execute(
            "SELECT o.settings_json,s.payload,s.revision FROM hub_schedule_attempts o "
            "JOIN hub_schedules s ON s.id=o.schedule_id WHERE schedule_id=? AND local_date=? "
            "AND slot=? AND attempt=? AND s.deleted_at IS NULL",
            (identifier, local_date, slot, attempt),
        ).fetchone()
        if not row:
            return
        settings, current = json.loads(row[0]), json.loads(row[1])
        if (
            attempt >= settings.get("max_retries", 0)
            or not current["enabled"]
            or settings.get("revision") != row[2]
        ):
            return
        due = now + timedelta(minutes=settings.get("retry_interval_minutes", 5))
        return bool(
            db.execute(
                "INSERT OR IGNORE INTO hub_schedule_attempts VALUES (?,?,?,?,?,'waiting',NULL,NULL,NULL,NULL,?,?)",
                (
                    identifier,
                    local_date,
                    slot,
                    attempt + 1,
                    due.astimezone(UTC).isoformat(),
                    "Aguardando nova tentativa após falha.",
                    row[0],
                ),
            ).rowcount
        )

    def active(self, windows_user):
        with self.store.connection() as db:
            return records(
                db.execute(
                    "SELECT o.* FROM hub_schedule_attempts o JOIN hub_schedules s ON s.id=o.schedule_id "
                    "WHERE s.machine_id=? AND s.windows_user=? AND o.state IN ('starting','running')",
                    (self.store.machine_id, windows_user.casefold()),
                )
            )

    def history(self, identifier, windows_user, *, page=0, size=20):
        with self.store.connection() as db:
            owner = db.execute(
                "SELECT 1 FROM hub_schedules WHERE id=? AND machine_id=? "
                "AND windows_user=? AND deleted_at IS NULL",
                (identifier, self.store.machine_id, windows_user.casefold()),
            ).fetchone()
            if not owner:
                raise KeyError(identifier)
            total = db.execute(
                "SELECT count(*) FROM hub_schedule_attempts WHERE schedule_id=?", (identifier,)
            ).fetchone()[0]
            rows = records(
                db.execute(
                    "SELECT local_date,slot,attempt,due_at,state,run_id,started_at,finished_at,message "
                    "FROM hub_schedule_attempts WHERE schedule_id=? ORDER BY due_at DESC,attempt DESC LIMIT ? OFFSET ?",
                    (identifier, size, page * size),
                )
            )
            return {"rows": rows, "total": total, "page": page, "page_size": size}
