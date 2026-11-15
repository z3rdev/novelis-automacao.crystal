from app.services.chamado_message import DEFAULT_COMPLEMENT, DEFAULT_MESSAGE, validate_template

KEYS = {"title": "NOVELIS_CHAMADO_TITULO", "signature": "NOVELIS_CHAMADO_ASSINATURA",
        "message": "NOVELIS_CHAMADO_MENSAGEM", "complement_message": "NOVELIS_CHAMADO_MENSAGEM_COMPLEMENTAR",
        "allow_missing_receipt": "NOVELIS_CHAMADO_ALLOW_MISSING_COMPROVANTE"}


def read(config, store=None) -> dict:
    if store:
        config.values.update(store.preferences())
    def get(key):
        return config.get(KEYS[key])
    return {"title": get("title") or "CTE {cte}", "signature": get("signature"),
            "message": get("message") or DEFAULT_MESSAGE,
            "complement_message": get("complement_message") or DEFAULT_COMPLEMENT,
            "allow_missing_receipt": get("allow_missing_receipt").lower() in {"1", "true", "sim", "yes"}}


def save(config, store, values: dict):
    for key in ("title", "message", "complement_message"):
        validate_template(values[key])
    updates = {env: str(values[key]) if key != "allow_missing_receipt" else str(values[key]).lower()
               for key, env in KEYS.items()}
    config.values.update(store.preferences(updates))
