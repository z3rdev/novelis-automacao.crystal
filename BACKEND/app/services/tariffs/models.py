"""Decimal amounts, inclusive validity dates and read-only tariff projections."""

import hashlib
import json
import re
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from .municipalities import city, normalized

ZONE = ZoneInfo("America/Sao_Paulo")


def decimal(value):
    text = re.sub(r"[^0-9.,+-]", "", str("" if value is None else value).replace("\xa0", ""))
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        result = Decimal(text)
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def day(value):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value or "").strip(), fmt).replace(tzinfo=ZONE).date()
        except ValueError:
            continue
    return None


def status(start, end, today):
    if start is None or end is not None and end < start:
        return "inconsistente"
    if start > today:
        return "futura"
    if end is not None and end < today:
        return "vencida"
    return "vigente"


TEXT = {
    "operacao": "desc_operacao",
    "transportadora": "transportadora",
    "faturamento": "faturamento",
    "grupoEmpresa": "grupo_empresa",
    "ramo": "ramo",
    "tipoTransporte": "tipo_transporte",
    "veiculo": "veiculo",
    "outrosCustos": "outros",
    "ranking": "ranking",
    "share": "share",
}


def project(raw, cities):
    if not str(raw.get("id", "")).isdigit() or not str(raw.get("rota_id", "")).isdigit():
        raise ValueError("O portal retornou uma tarifa sem identificação válida.")
    lookup = (
        cities
        if isinstance(cities, dict)
        else {normalized(value["portal_label"]): value for value in cities}
    )
    origin = lookup.get(normalized(raw.get("origem"))) or city(raw.get("origem"))
    dest = lookup.get(normalized(raw.get("destino"))) or city(raw.get("destino"))
    start, end = day(raw.get("inicio")), day(raw.get("fim"))
    value = {
        "id": f"{raw['rota_id']}:{raw['id']}",
        "idTarifa": str(raw["id"]),
        "idRota": str(raw["rota_id"]),
        **{
            key: str(raw.get(source) if raw.get(source) is not None else "").strip()
            for key, source in TEXT.items()
        },
        "origem": origin["label"],
        "destino": dest["label"],
        "origemPortal": str(raw.get("origem") or ""),
        "destinoPortal": str(raw.get("destino") or ""),
        "origemId": origin["portal_id"],
        "destinoId": dest["portal_id"],
        "origemIbge": origin["ibge"],
        "destinoIbge": dest["ibge"],
        "inicio": start.isoformat() if start else None,
        "fim": end.isoformat() if end else None,
        "inicioPortal": str(raw.get("inicio") or ""),
        "fimPortal": str(raw.get("fim") or ""),
    }
    for key, source in (
        ("tarifaTon", "tarifa"),
        ("valorTotal", "total"),
        ("capacidadeTon", "capacidade"),
        ("adValorem", "adValorem"),
    ):
        number = decimal(raw.get(source))
        value[key] = str(number) if number is not None else None
    # Missing/invalid dates must not accidentally become a current contract.
    value["vigenciaValida"] = bool(
        start
        and (end is None or end >= start)
        and (not str(raw.get("fim") or "").strip() or end is not None)
    )
    return value


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def next_check(rows, now):
    today = now.astimezone(ZONE).date()
    dates = [today + timedelta(days=1)]
    for row in rows:
        if not row["vigenciaValida"]:
            continue
        start, end = day(row["inicio"]), day(row["fim"])
        if start and start > today:
            dates.append(start)
        if start and start <= today and end and end >= today:
            dates.append(end + timedelta(days=1))
    return datetime.combine(min(dates), time.min, ZONE)


def estimate(value, tonnes, today=None):
    if not re.fullmatch(r"\d{1,6}(?:[.,]\d{1,6})?", str(tonnes).strip()):
        raise ValueError("Informe a tonelagem usando apenas números e separador decimal.")
    weight, rate = decimal(tonnes), decimal(value.get("tarifaTon"))
    if weight is None or not Decimal(0) < weight <= Decimal(100000):
        raise ValueError("Informe uma tonelagem maior que zero e até 100.000 t.")
    if rate is None or rate < 0:
        raise ValueError("A tarifa não possui valor por tonelada válido.")
    today = today or datetime.now(ZONE).date()
    capacity = decimal(value.get("capacidadeTon"))
    return {
        "idTarifa": value["idTarifa"],
        "toneladas": str(weight),
        "tarifaTon": str(rate),
        "valor": str((weight * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "status": status(day(value.get("inicio")), day(value.get("fim")), today)
        if value["vigenciaValida"]
        else "inconsistente",
        "excedeCapacidade": bool(capacity is not None and weight > capacity),
    }
