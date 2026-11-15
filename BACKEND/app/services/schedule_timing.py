"""Local calendar slots and persisted retry deadlines for one schedule."""

from datetime import datetime, time, timedelta


def next_occurrence(value, now, *, today_only=False):
    if not value["enabled"]:
        return None
    history = value.get("occurrences", [])
    candidates = []
    for row in history:
        if row["state"] == "waiting":
            candidates.append(
                {
                    "local_date": row["local_date"],
                    "slot": row["slot"],
                    "attempt": row["attempt"],
                    "due_at": datetime.fromisoformat(row["due_at"]),
                }
            )
    consumed = {(row["local_date"], row["slot"]) for row in history}
    # Compatibility with pre-upgrade responses that carry only the last result.
    if not history and (last := value.get("last_run")):
        consumed.add((last["local_date"], last.get("slot", 0)))
    activated = datetime.fromisoformat(value["activated_at"])
    for offset in range(1 if today_only else 8):
        day = now.date() + timedelta(days=offset)
        if day.weekday() not in value["weekdays"]:
            continue
        first = datetime.combine(day, time.fromisoformat(value["time"]), tzinfo=now.tzinfo)
        for slot in range(value.get("runs_per_day", 1)):
            due = first + timedelta(minutes=slot * value.get("interval_minutes", 60))
            if due >= activated and (day.isoformat(), slot) not in consumed:
                candidates.append(
                    {"local_date": day.isoformat(), "slot": slot, "attempt": 0, "due_at": due}
                )
    return min(candidates, key=lambda row: row["due_at"]) if candidates else None
