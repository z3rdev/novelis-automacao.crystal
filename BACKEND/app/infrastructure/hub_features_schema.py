FEATURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS hub_notifications (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
    severity TEXT NOT NULL, author TEXT NOT NULL, created_at TEXT NOT NULL,
    expires_at TEXT, archived_at TEXT);
CREATE TABLE IF NOT EXISTS hub_notification_reads (
    notification_id TEXT NOT NULL REFERENCES hub_notifications(id),
    windows_user TEXT NOT NULL, read_at TEXT NOT NULL, machine_id TEXT NOT NULL,
    PRIMARY KEY(notification_id, windows_user));
CREATE TABLE IF NOT EXISTS hub_schedules (
    id TEXT PRIMARY KEY, machine_id TEXT NOT NULL, windows_user TEXT NOT NULL,
    payload TEXT NOT NULL, revision INTEGER NOT NULL,
    activated_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT);
CREATE INDEX IF NOT EXISTS ix_hub_schedules_owner ON hub_schedules(machine_id, windows_user);
CREATE TABLE IF NOT EXISTS hub_schedule_occurrences (
    schedule_id TEXT NOT NULL REFERENCES hub_schedules(id), local_date TEXT NOT NULL,
    state TEXT NOT NULL, run_id TEXT, session_id TEXT,
    started_at TEXT NOT NULL, finished_at TEXT, message TEXT NOT NULL,
    settings_json TEXT NOT NULL, PRIMARY KEY(schedule_id, local_date));
CREATE TABLE IF NOT EXISTS hub_schedule_attempts (
    schedule_id TEXT NOT NULL REFERENCES hub_schedules(id), local_date TEXT NOT NULL,
    slot INTEGER NOT NULL, attempt INTEGER NOT NULL, due_at TEXT NOT NULL,
    state TEXT NOT NULL, run_id TEXT, session_id TEXT, started_at TEXT,
    finished_at TEXT, message TEXT NOT NULL, settings_json TEXT NOT NULL,
    PRIMARY KEY(schedule_id, local_date, slot, attempt));
CREATE INDEX IF NOT EXISTS ix_schedule_attempts_state ON hub_schedule_attempts(state,due_at);
INSERT OR IGNORE INTO hub_schedule_attempts
    (schedule_id,local_date,slot,attempt,due_at,state,run_id,session_id,
     started_at,finished_at,message,settings_json)
SELECT schedule_id,local_date,0,0,started_at,state,run_id,session_id,
       started_at,finished_at,message,settings_json FROM hub_schedule_occurrences;
"""
