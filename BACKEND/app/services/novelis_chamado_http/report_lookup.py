"""Match a fiscal identity and search through the day the ticket can be opened."""

from datetime import datetime

from app.data.chamados_reader import search_chamado_rows
from app.services.tariffs.audit import issued


def report_period(row, fallback, today=None):
    date = issued(row)
    if date is None:
        return fallback
    today = today or datetime.now().astimezone().date()
    return {"startBR": min(date, today).strftime("%d/%m/%Y"),
            "endBR": max(date, today).strftime("%d/%m/%Y")}


def existing_number(records, row):
    records = [{**item, "chamado": item.get("chamado") or item.get("chamadoNumero")} for item in records]
    hit = search_chamado_rows(records, row.get("filial"), row.get("serie"), row.get("documento"), row.get("cteId"))
    return str(hit.get("chamado") or "") if hit else ""
