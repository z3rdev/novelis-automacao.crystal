"""Identify an archived CT-e by its XML contents, rather than a partial filename."""

import re
from pathlib import Path
from xml.etree import ElementTree as ET

from app.automation.cancellation import check_cancelled

NS = {"cte": "http://www.portalfiscal.inf.br/cte"}


def validate_download(path: Path, row: dict) -> None:
    if not path.is_file() or not 0 < path.stat().st_size <= 20 * 1024 * 1024:
        raise ValueError("Arquivo XML vazio ou maior que o limite de 20 MB.")
    root = ET.parse(path).getroot()
    info = root.find(".//cte:infCte", NS)
    if info is None or root.tag.split("}")[-1] not in {"CTe", "cteProc"}:
        raise ValueError("O arquivo recebido nao e um XML de CT-e.")
    key = info.get("Id", "").removeprefix("CTe")
    expected = str(row.get("cteId") or row.get("CTE_ID") or "").removeprefix("CTe")
    if not re.fullmatch(r"\d{44}", key) or (expected and key != expected):
        raise ValueError("A chave dentro do XML nao corresponde ao CT-e consultado.")
    for field, tag in (("serie", "serie"), ("documento", "nCT")):
        value = row.get(field)
        actual = info.findtext(f"cte:ide/cte:{tag}", namespaces=NS)
        if value is not None and (actual is None or int(actual) != int(value)):
            raise ValueError("Serie/numero dentro do XML nao corresponde ao CT-e consultado.")


def matching_xml_files(directory: Path, row: dict, *, entries: list[Path] | None = None) -> list[Path]:
    if not directory.is_dir():
        return []
    doc = str(int(row["documento"]))
    expected = str(row.get("cteId") or row.get("CTE_ID") or "").removeprefix("CTe")
    cte = "-".join(str(int(row[k])) for k in ("filial", "serie", "documento"))
    candidates = [directory / f"CTE_{cte}.xml"]
    for path in directory.iterdir() if entries is None else entries:
        check_cancelled()
        if path.suffix.lower() == ".xml" and (doc in path.stem or expected and expected in path.stem):
            candidates.append(path)
    legacy = directory / f"cte-{doc}"
    if legacy.is_dir():
        candidates.extend(legacy.glob("*.xml"))
    found = []
    for path in dict.fromkeys(candidates):
        check_cancelled()
        # Without the access key, require the explicit filial-serie-documento name.
        if not expected and path.name.lower() != f"cte_{cte}.xml":
            continue
        try:
            validate_download(path, row)
        except (OSError, ValueError, ET.ParseError):
            continue
        found.append(path)
    return found
