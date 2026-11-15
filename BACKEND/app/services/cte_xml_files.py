"""Identify an archived CT-e by its XML contents, rather than a partial filename."""

import re
from pathlib import Path
from xml.etree import ElementTree as ET

from app.automation.cancellation import check_cancelled

NS = {"cte": "http://www.portalfiscal.inf.br/cte"}


def read_xml_identity(path: Path):
    # A bounded read validates existence and size with one file handle, instead
    # of multiple SMB metadata round trips before opening the same document.
    with path.open("rb") as file:
        content = file.read(20 * 1024 * 1024 + 1)
    if not 0 < len(content) <= 20 * 1024 * 1024:
        raise ValueError("Arquivo XML vazio ou maior que o limite de 20 MB.")
    root = ET.fromstring(content)
    info = root.find(".//cte:infCte", NS)
    if info is None or root.tag.split("}")[-1] not in {"CTe", "cteProc"}:
        raise ValueError("O arquivo recebido nao e um XML de CT-e.")
    key = info.get("Id", "").removeprefix("CTe")
    if not re.fullmatch(r"\d{44}", key):
        raise ValueError("O XML não contém uma chave de CT-e válida.")
    return (
        key,
        info.findtext("cte:ide/cte:serie", namespaces=NS),
        info.findtext("cte:ide/cte:nCT", namespaces=NS),
    )


def validate_xml_identity(identity, row):
    key, serie, number = identity
    expected = str(row.get("cteId") or row.get("CTE_ID") or "").removeprefix("CTe")
    if expected and key != expected:
        raise ValueError("A chave dentro do XML nao corresponde ao CT-e consultado.")
    for field, actual in (("serie", serie), ("documento", number)):
        value = row.get(field)
        if value is not None and (actual is None or int(actual) != int(value)):
            raise ValueError("Serie/numero dentro do XML nao corresponde ao CT-e consultado.")


def validate_download(path: Path, row: dict) -> None:
    validate_xml_identity(read_xml_identity(path), row)


def matching_xml_files(
    directory: Path,
    row: dict,
    *,
    entries: list[Path] | None = None,
    files=None,
    first_only=False,
    validator=validate_download,
) -> list[Path]:
    if files is None and not directory.is_dir():
        return []
    doc = str(int(row["documento"]))
    expected = str(row.get("cteId") or row.get("CTE_ID") or "").removeprefix("CTe")
    cte = "-".join(str(int(row[k])) for k in ("filial", "serie", "documento"))
    if files is not None:
        entries = files(directory, {".xml"})
    candidates = (
        [path for path in entries if path.name.casefold() == f"cte_{cte}.xml"]
        if files is not None
        else [directory / f"CTE_{cte}.xml"]
    )
    if first_only:
        for path in candidates:
            check_cancelled()
            try:
                validator(path, row)
                return [path]
            except (OSError, ValueError, ET.ParseError):
                continue
    for path in directory.iterdir() if entries is None else entries:
        check_cancelled()
        if path.suffix.lower() == ".xml" and (
            doc in path.stem or expected and expected in path.stem
        ):
            candidates.append(path)
    legacy = directory / f"cte-{doc}"
    if files is not None:
        candidates.extend(files(legacy, {".xml"}))
    elif legacy.is_dir():
        candidates.extend(legacy.glob("*.xml"))
    found = []
    for path in dict.fromkeys(candidates):
        check_cancelled()
        # Without the access key, require the explicit filial-serie-documento name.
        if not expected and path.name.lower() != f"cte_{cte}.xml":
            continue
        try:
            validator(path, row)
        except (OSError, ValueError, ET.ParseError):
            continue
        found.append(path)
        if first_only:
            return found
    return found
