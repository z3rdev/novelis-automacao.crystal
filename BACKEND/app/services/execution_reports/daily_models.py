"""Daily business totals derived from confirmed openings across all operators."""

import json
from datetime import datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from .models import timestamp
from .workbook import ZONE


def confirmed_at(item, report):
    for value in (item.get("confirmado_em"), report.get("finished_at"), report.get("started_at")):
        if value:
            try:
                parsed = datetime.fromisoformat(value)
                return parsed.replace(tzinfo=ZONE) if parsed.tzinfo is None else parsed
            except ValueError:
                continue
    raise ValueError("Abertura confirmada sem uma data válida.")


def consolidate(reports):
    tickets = {}
    for report in reports:
        for item in report.get("opened", []):
            moment = confirmed_at(item, report)
            value = {
                **item,
                "confirmado_em": moment.isoformat(),
                "operator": report["operator"],
                "computer": report["computer"],
                "run_id": report["id"],
            }
            key = str(item.get("numero") or item["cte"])
            previous = tickets.get(key)
            if previous is None or moment < datetime.fromisoformat(previous["confirmado_em"]):
                tickets[key] = value
    days = {}
    for report in reports:
        if report.get("generate_requested") and report.get("requested_report_date"):
            days.setdefault(report["requested_report_date"], [])
    for item in sorted(
        tickets.values(),
        key=lambda row: (datetime.fromisoformat(row["confirmado_em"]), row.get("numero", "")),
    ):
        day = datetime.fromisoformat(item["confirmado_em"]).astimezone(ZONE).date().isoformat()
        days.setdefault(day, []).append(item)
    return {day: daily_report(day, opened) for day, opened in days.items()}


def daily_report(day, opened):
    operators = sorted({item["operator"] for item in opened})
    computers = sorted({item["computer"] for item in opened})
    return {
        "id": daily_id(day),
        "kind": "daily",
        "report_date": day,
        "operator": ", ".join(operators),
        "computer": ", ".join(computers),
        "operators": operators,
        "computers": computers,
        "run_count": len({item["run_id"] for item in opened}),
        "flow": "daily",
        "status": "completed",
        "started_at": opened[0]["confirmado_em"] if opened else timestamp(),
        "finished_at": opened[-1]["confirmado_em"] if opened else timestamp(),
        "generated_at": timestamp(),
        "opened": opened,
        "opened_count": len(opened),
        "existing": [],
        "existing_count": 0,
        "source_revision": sha256(json.dumps(opened, sort_keys=True).encode()).hexdigest(),
        "share_status": "pending",
        "share_message": "Relatório diário atualizado; envio ao MinIO pendente.",
    }


def daily_id(day):
    return str(uuid5(NAMESPACE_URL, f"cargo-hub:chamados:{day}"))
