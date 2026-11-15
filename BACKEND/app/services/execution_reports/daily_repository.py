import json

from .models import identifier


class DailyRepository:
    def __init__(self, store):
        self.store = store

    def ensure(self):
        with self.store.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS execution_daily_reports (
                report_date TEXT PRIMARY KEY, id TEXT UNIQUE NOT NULL,
                payload TEXT NOT NULL, updated_at TEXT NOT NULL)""")

    def get(self, report_id):
        self.ensure()
        with self.store.connection() as db:
            row = db.execute(
                "SELECT payload FROM execution_daily_reports WHERE id=?", (identifier(report_id),)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, value):
        self.ensure()
        with self.store.connection() as db:
            db.execute(
                """INSERT INTO execution_daily_reports VALUES (?,?,?,?)
                ON CONFLICT(report_date) DO UPDATE SET
                payload=excluded.payload,updated_at=excluded.updated_at""",
                (value["report_date"], value["id"], json.dumps(value), value["generated_at"]),
            )

    def page(self, page=0, size=30):
        self.ensure()
        with self.store.connection() as db:
            total = db.execute("SELECT COUNT(*) FROM execution_daily_reports").fetchone()[0]
            rows = db.execute(
                """SELECT json_remove(payload,'$.opened','$.existing')
                FROM execution_daily_reports ORDER BY report_date DESC LIMIT ? OFFSET ?""",
                (size, page * size),
            ).fetchall()
        return {
            "rows": [json.loads(row[0]) for row in rows],
            "total": total,
            "page": page,
            "page_size": size,
        }

    def pending(self):
        self.ensure()
        with self.store.connection() as db:
            rows = db.execute("""SELECT id FROM execution_daily_reports
                WHERE json_extract(payload,'$.share_status')!='shared'
                OR julianday(json_extract(payload,'$.private_url_expires'))<julianday('now','+1 day')
                ORDER BY report_date DESC LIMIT 20""").fetchall()
        return [row[0] for row in rows]
