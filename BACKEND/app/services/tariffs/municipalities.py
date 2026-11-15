"""Match portal city labels to IBGE names, never confusing portal IDs with IBGE."""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)))


@lru_cache(maxsize=1)
def reference():
    root = Path(__file__).parents[2] / "resources/municipios"
    states = {
        row["codigo_uf"]: row["uf"]
        for row in json.loads((root / "estados.json").read_text(encoding="utf-8-sig"))
    }
    cities = json.loads((root / "municipios.json").read_text(encoding="utf-8-sig"))
    result = {}
    for city in cities:
        uf = states[city["codigo_uf"]]
        value = {
            "ibge": city["codigo_ibge"],
            "uf": uf,
            "nome": city["nome"],
            "label": f"{uf}-{city['nome']}",
        }
        result[normalized(value["label"])] = value
    return result


def city(label, portal_id=None):
    raw = str(label or "").strip()
    match = reference().get(normalized(raw))
    return {
        "portal_id": str(portal_id or ""),
        "portal_label": raw,
        "ibge": match["ibge"] if match else None,
        "uf": match["uf"]
        if match
        else (raw[:2].upper() if re.match(r"^[A-Za-z]{2}\s*-", raw) else ""),
        "nome": match["nome"] if match else raw.split("-", 1)[-1].strip(),
        "label": match["label"] if match else raw,
        "matched": bool(match),
    }


def portal_cities(options):
    values = {}
    for field in ("origem", "destino"):
        for option in options.get(field, []):
            if str(option.get("value") or "").isdigit() and option.get("label"):
                value = city(option["label"], option["value"])
                values[value["portal_id"]] = value
    return list(values.values())
