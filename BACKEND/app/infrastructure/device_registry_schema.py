"""Additive inventory schema shared with the existing session audit database."""

DEVICE_COLUMNS = (
    "id", "machine_id", "computer_name", "windows_user", "mac_addresses", "version",
    "installation_kind", "install_root", "first_seen_at", "last_seen_at", "instance_id",
    "backend_started_at", "backend_status", "automation_status", "run_id", "updated_at",
)

DEVICE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS devices (
        id TEXT PRIMARY KEY, machine_id TEXT NOT NULL, computer_name TEXT NOT NULL,
        windows_user TEXT NOT NULL, mac_addresses TEXT NOT NULL, version TEXT NOT NULL,
        installation_kind TEXT NOT NULL, install_root TEXT NOT NULL,
        first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, instance_id TEXT NOT NULL,
        backend_started_at TEXT NOT NULL, backend_status TEXT NOT NULL,
        automation_status TEXT NOT NULL, run_id TEXT, updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS ix_devices_seen ON devices(last_seen_at);
"""


def apply_device(db, value: dict) -> None:
    updates = ",".join(f"{key}=excluded.{key}" for key in DEVICE_COLUMNS if key not in {"id", "first_seen_at"})
    db.execute(f"INSERT INTO devices ({','.join(DEVICE_COLUMNS)}) "
        f"VALUES ({','.join('?' for _ in DEVICE_COLUMNS)}) ON CONFLICT(id) DO UPDATE SET "
        f"first_seen_at=MIN(devices.first_seen_at,excluded.first_seen_at),{updates} "
        "WHERE excluded.updated_at>=devices.updated_at AND "
        "(excluded.backend_status!='stopped' OR excluded.instance_id=devices.instance_id)",
        tuple(value.get(key) for key in DEVICE_COLUMNS))
