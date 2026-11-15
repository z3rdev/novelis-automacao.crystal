from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font

from app.api.deps import get_settings_from_app
from app.config.settings import Settings
from app.services.pending_plan_view import _load_plan_rows

router = APIRouter(prefix="/pendentes", tags=["pendentes"])

COMPROVANTE_LABELS = {
    "ok": "OK",
    "falta": "Falta",
    "nao_exige": "Não exige",
}




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
