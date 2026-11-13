import re
import shutil
import zipfile
from pathlib import Path
from typing import Any


def resolve_chamado_upload_files(cwd: Path, config: dict[str, Any], row: dict[str, Any]) -> dict[str, str]:
    cte = _cte(row)
    documento = _part(row.get("documento"))
    if not cte or not documento:
        raise RuntimeError("CTE do chamado não foi identificado para resolver anexos.")

    evidence = config.get("evidence") if isinstance(config.get("evidence"), dict) else {}
    pdf_source = _existing_path(cwd, evidence.get("pdfFile"))
    xml_source = _existing_path(cwd, evidence.get("xmlFile"))
    zip_evidence = evidence.get("comprovanteZipFiles")
    if zip_evidence is None:
        zip_evidence = evidence.get("comprovanteFiles") or []
    comprovantes = [_existing_path(cwd, value) for value in zip_evidence]
    comprovantes = [value for value in comprovantes if value]

    if not pdf_source:
        pdf_source = _find_evidence_file(cwd, config, row, "pdf")
    if not xml_source:
        xml_source = _find_evidence_file(cwd, config, row, "xml")

    target_dir = _resolve(cwd, config.get("chamadoDownloadTargetDir") or "captures/tarifario-downloads")
    cte_dir = target_dir / f"cte-{_slug(documento)}"
    cte_dir.mkdir(parents=True, exist_ok=True)

    pdf_target = _copy_named(pdf_source, cte_dir / f"CTRC_{_safe_base(cte)}.pdf")
    xml_target = _copy_named(xml_source, cte_dir / f"CTE_{_safe_base(cte)}.xml")
    zip_file = _build_zip(cwd, config, row, xml_target, comprovantes)

    missing = []
    if not pdf_target:
        missing.append("PDF")
    if not xml_target:
        missing.append("XML")
    if not zip_file:
        missing.append("ZIP")
    if missing:
        raise RuntimeError(f"Arquivos obrigatórios para upload não encontrados: {', '.join(missing)}.")

    return {
        "documento": documento,
        "idTarifario": str(row.get("idTarifario") or "sem-id"),
        "pdfFile": str(pdf_target),
        "xmlFile": str(xml_target),
        "zipFile": str(zip_file),
    }


def _existing_path(cwd: Path, value: Any) -> Path | None:
    path = _resolve(cwd, value)
    return path if path and path.is_file() else None


def _resolve(cwd: Path, value: Any) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else cwd / path


def _find_evidence_file(cwd: Path, config: dict[str, Any], row: dict[str, Any], kind: str) -> Path | None:
    if kind == "pdf":
        dirs = [
            config.get("chamadoDownloadTargetDir") or "captures/tarifario-downloads",
            config.get("chamadoPdfSourceDir") or "captures/rodopar-pdfs-downloads",
        ]
    else:
        dirs = [
            config.get("chamadoDownloadTargetDir") or "captures/tarifario-downloads",
            config.get("chamadoXmlSourceDir") or "captures/cte-fazenda-downloads",
        ]

    candidates = []
    for raw_dir in dirs:
        base_dir = _resolve(cwd, raw_dir)
        if not base_dir or not base_dir.exists():
            continue
        for file_path in base_dir.rglob(f"*.{kind}"):
            score = _score_file(file_path, row, kind)
            if score > 0:
                candidates.append((score, file_path.stat().st_mtime, file_path))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2] if candidates else None


def _score_file(file_path: Path, row: dict[str, Any], kind: str) -> int:
    cte = _cte(row).lower()
    documento = _part(row.get("documento")).lower()
    base = file_path.name.lower()
    parent = file_path.parent.name.lower()
    prefix = "ctrc" if kind == "pdf" else "cte"
    score = 0
    if base == f"{prefix}_{cte}.{kind}":
        score += 500
    if base.startswith(f"{prefix}_{cte}"):
        score += 450
    if cte and cte in base:
        score += 300
    if documento and parent == f"cte-{documento}":
        score += 120
    if documento and documento in base:
        score += 30
    return score


def _copy_named(source: Path | None, target: Path) -> Path | None:
    if not source or not source.is_file():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or source.stat().st_size != target.stat().st_size:
        shutil.copy2(source, target)
    return target


def _build_zip(cwd: Path, config: dict[str, Any], row: dict[str, Any], xml_file: Path | None, extras: list[Path]) -> Path | None:
    if not xml_file or not xml_file.is_file():
        return None
    zip_dir = _resolve(cwd, config.get("chamadoZipDir") or "captures/tarifario-zips")
    if not zip_dir:
        return None
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"tarifa-{_slug(row.get('idTarifario') or _cte(row) or 'sem-id')}.zip"
    zip_path = zip_dir / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(xml_file, xml_file.name)
        for extra in extras:
            if extra and extra.is_file():
                archive.write(extra, extra.name)
    return zip_path if zip_path.is_file() else None


def _cte(row: dict[str, Any]) -> str:
    parts = [_part(row.get("filial")), _part(row.get("serie")), _part(row.get("documento"))]
    return "-".join(part for part in parts if part) or str(row.get("numeroCte") or "").strip()


def _part(value: Any) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits.lstrip("0") or digits


def _safe_base(value: Any) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", str(value or "cte")).strip("_") or "cte"


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "item").lower()).strip("-")[:60] or "item"
