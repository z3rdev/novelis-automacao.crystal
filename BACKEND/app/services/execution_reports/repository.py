import json

from .models import identifier


class ReportRepository:
    def __init__(self, store):
        self.store = store

    def ensure(self):
        with self.store.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS execution_reports (
                run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)""")

    def get(self, run_id):
        self.ensure()
        with self.store.connection() as db:
            row = db.execute(
                "SELECT payload FROM execution_reports WHERE run_id=?", (identifier(run_id),)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, value):
        self.ensure()
        with self.store.connection() as db:
            db.execute(
                """INSERT INTO execution_reports VALUES (?,?,?) ON CONFLICT(run_id)
                DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at""",
                (
                    identifier(value["id"]),
                    json.dumps(value, ensure_ascii=False),
                    value["generated_at"],
                ),
            )

    def page(self, page=0, size=30):
        self.ensure()
        with self.store.connection() as db:
            total = db.execute(
                "SELECT COUNT(*) FROM execution_reports WHERE json_extract(payload,'$.status')!='running'"
            ).fetchone()[0]
            rows = db.execute(
                """SELECT json_remove(payload,'$.opened','$.existing') FROM execution_reports
                WHERE json_extract(payload,'$.status')!='running' ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
                (size, page * size),
            ).fetchall()
        return {
            "rows": [json.loads(row[0]) for row in rows],
            "total": total,
            "page": page,
            "page_size": size,
        }

    def events(self, run_id):
        # No 1,000-event UI limit: a large execution must retain every confirmed save.
        with self.store.connection() as db:
            rows = db.execute(
                """SELECT payload FROM execution_events WHERE run_id=?
                AND json_extract(payload,'$.kind') IN ('novelis.save','novelis.chamado_exists')
                ORDER BY id""",
                (identifier(run_id),),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def pending(self):
        self.ensure()
        with self.store.connection() as db:
            rows = db.execute("""SELECT payload FROM execution_reports
                WHERE json_extract(payload,'$.status')!='running'
                AND (json_extract(payload,'$.share_status')!='shared'
                     OR julianday(json_extract(payload,'$.private_url_expires'))<julianday('now','+1 day'))
                ORDER BY updated_at LIMIT 20""").fetchall()
        return [json.loads(row[0]) for row in rows]

    def completed(self):
        self.ensure()
        with self.store.connection() as db:
            rows = db.execute("""SELECT payload FROM execution_reports
                WHERE json_extract(payload,'$.status') IN ('completed','failed','cancelled')
                AND (json_extract(payload,'$.opened_count') > 0
                     OR json_extract(payload,'$.generate_requested')=1) ORDER BY run_id""").fetchall()
        return [json.loads(row[0]) for row in rows]

    def unfinished(self):
        self.ensure()
        with self.store.connection() as db:
            rows = db.execute("""SELECT r.payload FROM execution_runs r JOIN execution_reports p ON p.run_id=r.id
                WHERE json_extract(p.payload,'$.status')='running'
                AND json_extract(r.payload,'$.status') IN ('completed','failed','cancelled') LIMIT 20""").fetchall()
        return [json.loads(row[0]) for row in rows]
