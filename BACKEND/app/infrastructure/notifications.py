from datetime import UTC, datetime
from uuid import uuid4

from app.domain.hub_features import NotificationInput


class NotificationRepository:
    def __init__(self, store):
        self.store = store

    def publish(self, body: NotificationInput, actor: dict) -> dict:
        now = datetime.now(UTC)
        if body.expires_at and body.expires_at <= now:
            raise ValueError("A expiração precisa ser futura.")
        value = {"id": str(uuid4()), **body.model_dump(mode="json"), "author": actor["operator_name"],
                 "created_at": now.isoformat(), "archived_at": None}
        with self.store.connection() as db:
            db.execute("INSERT INTO hub_notifications VALUES (?,?,?,?,?,?,?,?)",
                (value["id"], value["title"], value["body"], value["severity"], value["author"],
                 value["created_at"], value["expires_at"], None))
            db.execute("INSERT INTO hub_notification_reads VALUES (?,?,?,?)",
                (value["id"], actor["windows_user"].casefold(), value["created_at"], self.store.machine_id))
        return value

    def synchronize(self, values: list[dict]) -> None:
        with self.store.connection() as db:
            db.executemany("INSERT INTO hub_notifications VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "title=excluded.title,body=excluded.body,severity=excluded.severity,author=excluded.author,"
                "created_at=excluded.created_at,expires_at=excluded.expires_at,archived_at=excluded.archived_at",
                [(value["id"], value["title"], value["body"], value["severity"], value["author"],
                  value["created_at"], value["expires_at"], value["archived_at"]) for value in values])

    def list(self, windows_user: str, *, developer: bool = False) -> list[dict]:
        sql = """SELECT n.*, r.read_at FROM hub_notifications n
                 LEFT JOIN hub_notification_reads r ON r.notification_id=n.id AND r.windows_user=?"""
        params = [windows_user.casefold()]
        if not developer:
            sql += " WHERE n.archived_at IS NULL AND (n.expires_at IS NULL OR n.expires_at>?)"
            params.append(datetime.now(UTC).isoformat())
            sql += " ORDER BY (r.read_at IS NULL) DESC, CASE n.severity WHEN 'critical' THEN 2 WHEN 'warning' THEN 1 ELSE 0 END DESC, n.created_at DESC"
        else:
            sql += " ORDER BY n.created_at DESC"
        with self.store.connection() as db:
            cursor = db.execute(sql + " LIMIT 200", params)
            keys = [column[0] for column in cursor.description]
            return [dict(zip(keys, row)) for row in cursor.fetchall()]

    def read(self, identifier: str, windows_user: str) -> bool:
        timestamp = datetime.now(UTC).isoformat()
        with self.store.connection() as db:
            if not db.execute("SELECT 1 FROM hub_notifications WHERE id=?", (identifier,)).fetchone():
                return False
            db.execute("INSERT OR IGNORE INTO hub_notification_reads VALUES (?,?,?,?)",
                (identifier, windows_user.casefold(), timestamp, self.store.machine_id))
        return True

    def archive(self, identifier: str) -> bool:
        with self.store.connection() as db:
            return bool(db.execute("UPDATE hub_notifications SET archived_at=COALESCE(archived_at,?) WHERE id=?",
                                   (datetime.now(UTC).isoformat(), identifier)).rowcount)
