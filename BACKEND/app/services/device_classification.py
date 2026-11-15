"""Classify stored hostnames without inferring authorization or hardware facts."""

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def naming_rules():
    return json.loads((Path(__file__).parents[1] / "resources/device-naming.json").read_text(encoding="utf-8"))


def classify_computer_name(name: str) -> dict:
    rules = naming_rules()
    hostname = unicodedata.normalize("NFKD", str(name or "").strip().split(".")[0])
    hostname = "".join(char for char in hostname if not unicodedata.combining(char)).upper()
    tokens = [re.sub(r"[0-9]+$", "", token) for token in re.split(r"[-_\s]+", hostname) if token]
    result = {"rules_version": rules["version"], "source": "computer_name", "conflicts": []}
    for field in ("sector", "station_type", "branch"):
        candidates = tokens[:1] if field == "station_type" else tokens
        matches = [rule for rule in rules[field] if any(token in rule["aliases"] for token in candidates)]
        result[field] = {"code": matches[0]["code"], "label": matches[0]["label"]} if len(matches) == 1 else None
        if len(matches) > 1:
            result["conflicts"].append(field)
    return result
