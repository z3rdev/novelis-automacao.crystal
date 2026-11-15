from datetime import UTC, datetime
from uuid import UUID

from app.data.cte_fields import enrich


def identifier(value):
    return str(UUID(str(value)))


def timestamp():
    return datetime.now(UTC).isoformat()


def ticket(row, number):
    """Only business columns; never forward the full SQL row or portal result."""
    row = enrich(row)
    parts = [str(row.get(key) or "").strip() for key in ("filial", "serie", "documento")]
    audit = row.get("tariffAudit") or {}
    number = str(number or "").strip()
    return {
        "cte": "-".join(parts),
        "numero": number,
        "link": f"https://novelis.wtmh.com.br/portal/chamado/{number}" if number.isdigit() else "",
        "origem": audit.get("origem") or row.get("remCidade") or row.get("origem") or "",
        "destino": audit.get("destino") or row.get("desCidade") or row.get("destino") or "",
        "ton": str(row.get("ton") or ""),
        "id_tarifa": str(row.get("idTarifario") or ""),
        "valor": row.get("vlrTotal"),
        "frete": row.get("vlrTar"),
        "conferencia": audit.get("status") or "",
        "confirmado_em": timestamp(),
    }


def entries(events):
    opened, existing = {}, {}
    for event in events:
        payload = event.get("payload") or {}
        value = payload.get("ticket")
        if not isinstance(value, dict) or not value.get("cte") or value["cte"] == "--":
            continue
        key = (value["cte"], value.get("numero") or "")
        result = payload.get("result") or {}
        if (
            event["kind"] == "novelis.save"
            and result.get("ok") is True
            and not result.get("duplicate")
        ):
            opened[key] = value
        elif event["kind"] == "novelis.chamado_exists":
            existing[key] = value
    return list(opened.values()), list(existing.values())


def public(value, detail=False):
    excluded = {
        "private_url",
        "private_url_expires",
        "object_key",
        "sha256",
        "local_file",
        "source_revision",
    }
    if not detail:
        excluded |= {"opened", "existing"}
    return {key: item for key, item in value.items() if key not in excluded}
