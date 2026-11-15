import re
from urllib.parse import urlsplit, urlunsplit
from app.services.hub_views import chamado_view


def ticket_url(number, config):
    number = str(number or "").strip()
    if not re.fullmatch(r"[0-9]{4,25}", number):
        return None
    base = str(config.novelis().get("chamadoDiretoUrl") or "")
    parsed = urlsplit(base)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        return None
    # This is the same /portal/chamado/{number} route recognized by the save flow.
    path = parsed.path.rstrip("/")
    if not path.endswith("/chamado"):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, path + "/" + number, "", ""))


def detail_view(record, config):
    raw = record["raw_payload"]
    value = {**chamado_view(raw), "id": record["id"]}
    digits = re.sub(r"\D", "", str(raw.get("cteId") or record.get("chave") or ""))
    return {**value, "chave": digits if len(digits) == 44 else "",
            "statusOriginal": str(raw.get("andamento") or ""),
            "portalUrl": ticket_url(value["chamado"], config),
            "sincronizadoEm": record["updated_at"].isoformat(),
            "descricao": str(raw.get("descricao") or raw.get("observacao") or "")}
