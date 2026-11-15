"""Bounded machine-specific history, preserving HTTP confirmation evidence."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import PureWindowsPath
from urllib.parse import urlsplit

SAFE_DETAILS = {
    "cte",
    "run_id",
    "submitted",
    "transport",
    "status",
    "save_http",
    "readback_http",
    "confirmation_source",
    "attachments_visible",
    "number",
    "numeroChamado",
    "catalog_updated",
    "error_code",
    "sync_stage",
    "stage",
    "node_kind",
    "node_index",
    "node_count",
    "workflow_name",
}
SAFE_TICKET = {
    "cte",
    "numero",
    "origem",
    "destino",
    "ton",
    "id_tarifa",
    "valor",
    "frete",
    "conferencia",
    "confirmado_em",
}


def public_ticket_url(value):
    parsed = urlsplit(str(value or ""))
    tail = parsed.path.removeprefix("/portal/chamado/")
    return (
        f"https://novelis.wtmh.com.br/portal/chamado/{tail}"
        if parsed.scheme == "https" and parsed.hostname == "novelis.wtmh.com.br" and tail.isdigit()
        else ""
    )


def event_view(event, redactor):
    raw = event.get("payload") or {}
    details = {key: value for key, value in raw.items() if key in SAFE_DETAILS}
    details["run_id"] = event.get("run_id") or details.get("run_id")
    if isinstance(raw.get("attachments"), list):
        details["attachments"] = [
            PureWindowsPath(str(value)).name for value in raw["attachments"][:30]
        ]
    if raw.get("url"):
        details["url"] = public_ticket_url(raw["url"])
    if isinstance(raw.get("ticket"), dict):
        details["ticket"] = {
            key: value for key, value in raw["ticket"].items() if key in SAFE_TICKET
        }
    if isinstance(raw.get("result"), dict):
        details["result"] = {"ok": raw["result"].get("ok")}
    return redactor.clean(
        {
            "time": event.get("created_at") or event.get("time"),
            "severity": event.get("level", "info"),
            "source": event.get("kind", "event"),
            "message": event.get("message", ""),
            "details": details,
        }
    )


def collect_history(store, options, redactor):
    if not store or not store.path.is_file():
        return {"available": False, "runs": [], "http": [], "events_truncated": False}
    cutoff = (datetime.now(UTC) - timedelta(days=options.days_back)).isoformat()
    with store.connection() as db:
        records = db.execute(
            """SELECT payload FROM execution_runs
            WHERE json_extract(payload,'$.machine_id')=?
            AND julianday(coalesce(json_extract(payload,'$.started_at'),updated_at))>=julianday(?)
            ORDER BY updated_at DESC LIMIT ?""",
            (store.machine_id, cutoff, options.max_runs),
        ).fetchall()
        runs = [json.loads(row[0]) for row in records]
        ids = [run["id"] for run in runs]
        events = []
        if ids:
            placeholders = ",".join("?" for _ in ids)
            rows = db.execute(
                f"""SELECT payload FROM execution_events WHERE run_id IN ({placeholders})
                AND json_extract(payload,'$.machine_id')=? AND (
                  json_extract(payload,'$.level') IN ('error','warn') OR
                  json_extract(payload,'$.kind') IN ('run.started','run.completed','run.cancelled','novelis.save') OR
                  json_extract(payload,'$.kind') LIKE '%http%' OR
                  json_extract(payload,'$.payload.save_http') IS NOT NULL)
                ORDER BY id DESC LIMIT 1001""",
                (*ids, store.machine_id),
            ).fetchall()
            events = [event_view(json.loads(row[0]), redactor) for row in rows[:1000]]
    result = []
    for run in runs:
        filtered = [event for event in events if event["details"].get("run_id") == run["id"]]
        result.append(
            {
                **redactor.clean(
                    {
                        key: run.get(key)
                        for key in (
                            "id",
                            "flow",
                            "status",
                            "dry_run",
                            "started_at",
                            "finished_at",
                            "message",
                        )
                    }
                ),
                "events": filtered[:100],
                "events_truncated": len(filtered) > 100,
            }
        )
    http = [
        event
        for event in events
        if "http" in event["source"]
        or event["source"] == "novelis.save"
        or event["details"].get("save_http") is not None
    ]
    return {
        "available": True,
        "runs": result,
        "http": http[:300],
        "events_truncated": len(rows) > 1000 if ids else False,
        "http_truncated": len(http) > 300,
    }
