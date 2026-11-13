from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font

from app.api.deps import get_settings_from_app
from app.config.settings import Settings
from app.infrastructure.json_store import read_json

router = APIRouter(prefix="/pendentes", tags=["pendentes"])

COMPROVANTE_LABELS = {
    "ok": "OK",
    "falta": "Falta",
    "nao_exige": "Não exige",
}


def _load_plan_rows(settings: Settings) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = settings.backend_root.parent / "captures" / "pendentes" / "latest-python.json"
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}

    checked = payload.get("checked") if isinstance(payload.get("checked"), list) else []
    falta_pdf = set(payload.get("faltandoPdf") or [])
    falta_xml = set(payload.get("faltandoXml") or [])
    falta_comprovante = set(payload.get("faltandoComprovante") or [])
    pronto_chamado = set(payload.get("prontosChamado") or [])

    rows: list[dict[str, Any]] = []
    for item in checked:
        if not isinstance(item, dict):
            continue
        cte = str(item.get("cte") or "")
        row = item.get("row") if isinstance(item.get("row"), dict) else {}
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        comprovante_files = evidence.get("comprovanteFiles")
        requires_comprovante = bool(evidence.get("requiresComprovante"))
        comprovante_ok = bool(evidence.get("comprovanteOk"))
        comprovante_status = "nao_exige" if not requires_comprovante else ("ok" if comprovante_ok else "falta")
        rows.append(
            {
                "cte": cte,
                "filial": str(row.get("filial") or ""),
                "serie": str(row.get("serie") or ""),
                "documento": str(row.get("documento") or ""),
                "faltaPdf": cte in falta_pdf,
                "faltaXml": cte in falta_xml,
                "faltaComprovante": cte in falta_comprovante,
                "prontoChamado": cte in pronto_chamado,
                "pdfFile": str(evidence.get("pdfFile") or ""),
                "xmlFile": str(evidence.get("xmlFile") or ""),
                "comprovanteCount": len(comprovante_files) if isinstance(comprovante_files, list) else 0,
                "requiresComprovante": requires_comprovante,
                "hasGuia": bool(evidence.get("hasGuia")),
                "hasComprovanteFile": bool(evidence.get("hasComprovanteFile")),
                "comprovanteStatus": comprovante_status,
            }
        )

    meta = {
        "generatedAt": str(payload.get("generatedAt") or ""),
        "sourceFile": str(payload.get("sourceFile") or ""),
        "sheetName": str(payload.get("sheetName") or ""),
        "consultados": int(payload.get("consultados") or 0),
        "faltandoPdfCount": len(falta_pdf),
        "faltandoXmlCount": len(falta_xml),
        "faltandoComprovanteCount": len(falta_comprovante),
        "prontosChamadoCount": len(pronto_chamado),
    }
    return meta, rows


@router.get("/plan")
async def pendentes_plan(settings: Settings = Depends(get_settings_from_app)) -> dict[str, Any]:
    meta, rows = _load_plan_rows(settings)
    return {**meta, "total": len(rows), "rows": rows}


@router.get("/plan/export.xlsx")
async def pendentes_plan_export(
    scope: str = Query("todos", pattern="^(todos|faltantes)$"),
    settings: Settings = Depends(get_settings_from_app),
) -> StreamingResponse:
    _, rows = _load_plan_rows(settings)
    if scope == "faltantes":
        rows = [row for row in rows if not row["prontoChamado"]]

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "CTEs pendentes"

    headers = ["CTE", "Filial", "Série", "Documento", "PDF", "XML", "Comprovante", "Chamado"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for row in rows:
        sheet.append(
            [
                row["cte"],
                row["filial"],
                row["serie"],
                row["documento"],
                "Falta" if row["faltaPdf"] else "OK",
                "Falta" if row["faltaXml"] else "OK",
                COMPROVANTE_LABELS.get(row["comprovanteStatus"], "-"),
                "Pronto" if row["prontoChamado"] else "Aguardando",
            ]
        )

    for column_cells in sheet.columns:
        length = max((len(str(cell.value or "")) for cell in column_cells), default=10)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 10), 40)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    filename = f"ctes-pendentes-{datetime.now(timezone.utc):%Y%m%d-%H%M}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
