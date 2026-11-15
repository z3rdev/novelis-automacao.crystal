import csv
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


DATE_COLUMNS = ("DATA", "DATA_EMISSAO", "DT_EMISSAO", "DT", "DATA_CTE", "EMISSAO", "DATA_DOC")


@dataclass(frozen=True)
class ConsultaResult:
    source_file: str
    sheet_name: str
    total_rows: int
    valid_rows: int
    ignored_rows: int
    records: list[dict[str, Any]]


def normalize_header(value: Any) -> str:
    text = str(value or "").strip().upper()
    replacements = {
        "Á": "A",
        "À": "A",
        "Ã": "A",
        "Â": "A",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ó": "O",
        "Õ": "O",
        "Ô": "O",
        "Ú": "U",
        "Ç": "C",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


def as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_decimal(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        return float(value)

    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def format_currency_br(value: float | None) -> str:
    if value is None:
        return ""
    text = f"{value:,.2f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def parse_date(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, int | float):
        return datetime(1899, 12, 31) + timedelta(days=float(value))
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def format_date_br(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%d/%m/%Y")


def normalize_cte_origem(value: str | None) -> str | None:
    text = as_text(value)
    if not text:
        return None
    numbers = re.findall(r"\d+", text)
    return "-".join(numbers) if numbers else re.sub(r"\s+", " ", text)


def parse_observacao(value: Any) -> dict[str, Any]:
    observacao = re.sub(r"\s+", " ", as_text(value).replace("_x000D_", " ")).strip()
    percurso = re.search(r"\bPERCURSO\s*[:=]?\s*(\d+)\b", observacao, re.I)
    item_id = re.search(r"\bID\s*[:=]?\s*(\d+)\b", observacao, re.I)
    ton = re.search(r"\bTON(?:S|ELADAS?)?\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)\b", observacao, re.I)
    if ton is None:
        ton = re.search(r"(?<![\w.,-])([0-9]+(?:[.,][0-9]+)?)\s*TON(?:S|ELADAS?)?\b", observacao, re.I)
    tariff = re.search(r"\bID\s*(?:DO\s+)?TARIF[ÁA]RIO\s*[:=]?\s*(\d+)\b", observacao, re.I)
    origem = re.search(
        r"\bCTE\s+(?:DE\s+)?ORIGEM\b\s*[:|-]?\s*([0-9][0-9\s./-]*?)(?=\s*(?:\||;|$))",
        observacao,
        re.I,
    )
    return {
        "observacao": observacao,
        "percurso": percurso.group(1) if percurso else None,
        "id": item_id.group(1) if item_id else None,
        "ton": parse_decimal(ton.group(1)) if ton else None,
        "tonRaw": ton.group(1) if ton else None,
        "idTarifarioObservacao": tariff.group(1) if tariff else None,
        "isCteComplementarFrete": bool(re.search(r"\bCTE\s+COMPLEMENTAR\s+DE\s+FRETE\b", observacao, re.I)),
        "cteOrigem": normalize_cte_origem(origem.group(1) if origem else None),
    }


def resolve_existing_path(raw_path: str, cwd: Path) -> Path:
    path = Path(raw_path)
    candidates = [path if path.is_absolute() else cwd / path]
    if candidates[0].suffix.lower() == ".xlsx":
        candidates.append(candidates[0].with_suffix(".xls"))
    if candidates[0].suffix.lower() == ".xls":
        candidates.append(candidates[0].with_suffix(".xlsx"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def read_rows(path: Path, sheet_name: str = "") -> tuple[list[list[Any]], str]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.reader(handle)), "CSV"

    workbook = load_workbook(path, data_only=True, read_only=True)
    chosen = sheet_name or workbook.sheetnames[0]
    if chosen not in workbook.sheetnames:
        raise ValueError(f'A aba "{chosen}" não existe no arquivo {path}.')
    sheet = workbook[chosen]
    rows = [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
    return rows, chosen


def row_has_identity(row: list[Any]) -> bool:
    filial = re.sub(r"\D", "", as_text(row[0] if len(row) > 0 else ""))
    serie = re.sub(r"\D", "", as_text(row[1] if len(row) > 1 else ""))
    documento = re.sub(r"\D", "", as_text(row[2] if len(row) > 2 else ""))
    return bool(filial and serie and documento)


def record_from_row(headers: list[str], row: list[Any], sheet_row: int) -> dict[str, Any]:
    row_map = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
    obs = parse_observacao(row_map.get("OBSERVACAO"))
    data_raw = next((row_map[key] for key in DATE_COLUMNS if row_map.get(key)), None)
    rem_cidade = as_text(row_map.get("REM_CIDADE"))
    des_cidade = as_text(row_map.get("DES_CIDADE"))
    vlr_total = parse_decimal(row_map.get("VLR_TOTAL"))
    vlr_tar = parse_decimal(row_map.get("VLR_TAR"))
    outros = parse_decimal(row_map.get("OUTROS"))
    freval = parse_decimal(row_map.get("FREVAL"))
    vlr_frete_peso = parse_decimal(row_map.get("VLR_FRETE_PESO") or row_map.get("FRETE_PESO"))

    return {
        "sheetRow": sheet_row,
        "filial": as_text(row_map.get("FILIAL")),
        "serie": as_text(row_map.get("SERIE")),
        "documento": as_text(row_map.get("DOCUMENTO")),
        "dataBR": format_date_br(parse_date(data_raw)),
        "nmgre": as_text(row_map.get("NMGRE") or row_map.get("NMGNRE") or row_map.get("NM_GNRE")),
        "remCidade": rem_cidade,
        "desCidade": des_cidade,
        "estCol": as_text(row_map.get("ESTCOL") or row_map.get("EST_COL")),
        "estDes": as_text(row_map.get("ESTDES") or row_map.get("EST_DES")),
        "vlrTotal": vlr_total,
        "vlrTotalFormatted": format_currency_br(vlr_total),
        "vlrTar": vlr_tar,
        "vlrTarFormatted": format_currency_br(vlr_tar),
        "outros": outros,
        "outrosFormatted": format_currency_br(outros),
        "freval": freval,
        "frevalFormatted": format_currency_br(freval),
        "rota": f"{rem_cidade} X {des_cidade}" if rem_cidade and des_cidade else "",
        "numeroCte": as_text(row_map.get("DOCUMENTO")),
        "cteId": as_text(
            row_map.get("CTE_ID")
            or row_map.get("ID_CTE")
            or row_map.get("CHAVE_ACESSO")
            or row_map.get("CHAVE_DE_ACESSO")
            or row_map.get("CHAVE_CTE")
        ),
        "veiCodigo": as_text(row_map.get("VEI_CODIGO") or row_map.get("VEICULO")),
        "pedido": as_text(row_map.get("PEDIDO") or row_map.get("NR_PEDIDO")),
        "vlrFretePeso": vlr_frete_peso,
        "vlrFretePesoFormatted": format_currency_br(vlr_frete_peso),
        "fazendo": as_text(row_map.get("FAZENDO") or row_map.get("EM_PROCESSAMENTO")),
        "feito": as_text(row_map.get("FEITO") or row_map.get("PROCESSADO")),
        **obs,
    }


def read_consulta_rows(config: dict[str, Any], cwd: Path) -> ConsultaResult:
    source = resolve_existing_path(str(config.get("consultaFile") or ""), cwd)
    if not source.exists():
        raise FileNotFoundError(f"Arquivo de consulta não encontrado: {source}")

    rows, sheet_name = read_rows(source, str(config.get("consultaSheet") or ""))
    if not rows:
        return ConsultaResult(str(source), sheet_name, 0, 0, 0, [])

    start_index = max(1, int(config.get("consultaStartRow") or 2) - 1)
    headers = [normalize_header(value) for value in rows[0]]
    records: list[dict[str, Any]] = []
    ignored = 0

    for row_index in range(start_index, len(rows)):
        row = rows[row_index]
        if not row or all(as_text(value) == "" for value in row):
            continue
        if not row_has_identity(row):
            ignored += 1
            continue
        records.append(record_from_row(headers, row, row_index + 1))

    return ConsultaResult(str(source), sheet_name, len(rows), len(records), ignored, records)
