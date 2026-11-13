import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.services.crystal_reports.diagnostics import diagnose
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.service import CrystalReportError, CrystalReportService
from app.services.dacte_xml import XmlDacteService

router = APIRouter(prefix="/reports/dacte", tags=["reports"])


def get_crystal_service(request: Request) -> CrystalReportService:
    return request.app.state.crystal_reports


CrystalService = Annotated[CrystalReportService, Depends(get_crystal_service)]


@router.get("/files/{filename}", response_class=FileResponse)
def view_generated_pdf(filename: str, service: CrystalService) -> FileResponse:
    if not re.fullmatch(r"dacte-[0-9]+-[0-9A-Za-z]+-[0-9]+-[a-f0-9]{32}\.pdf", filename):
        raise HTTPException(status_code=404, detail="PDF gerado nao encontrado.")
    path = service.settings.storage_dir / "reports" / "dacte" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="PDF gerado nao encontrado.")
    return FileResponse(path, media_type="application/pdf", headers={
        "Cache-Control": "no-store", "Content-Disposition": f'inline; filename="{filename}"',
        "X-DACTE-Validation": "pending",
    })


def get_xml_service(request: Request) -> XmlDacteService:
    return request.app.state.dacte_xml


XmlService = Annotated[XmlDacteService, Depends(get_xml_service)]


@router.get("/inspect")
def inspect_report(service: CrystalService) -> dict:
    """Le tabelas, parametros e subrelatorios sem consultar o banco."""
    try:
        return service.inspect()
    except CrystalReportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/pdf", response_class=FileResponse)
def export_dacte(
    payload: DacteRequest,
    service: CrystalService,
) -> FileResponse:
    """Exporta um unico CTe diretamente pelo RPT, sem abrir o Rodopar."""
    try:
        output = service.export(payload)
    except CrystalReportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return FileResponse(
        output,
        media_type="application/pdf",
        filename=f"dacte-{payload.filial}-{payload.serie}-{payload.documento}.pdf",
        headers={"Cache-Control": "no-store", "X-DACTE-Validation": "pending"},
    )


@router.get("/diagnostics")
def report_diagnostics(service: CrystalService, connect: bool = False) -> dict:
    return diagnose(service, connect=connect)


@router.post("/pdf-from-xml", response_class=FileResponse)
def export_dacte_from_xml(payload: DacteRequest, service: XmlService) -> FileResponse:
    """Gera DACTE do XML arquivado, usando outro layout e sem Crystal/Rodopar."""
    try:
        output = service.export(payload)
    except CrystalReportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return FileResponse(
        output,
        media_type="application/pdf",
        filename=f"dacte-{payload.filial}-{payload.serie}-{payload.documento}-xml.pdf",
        headers={"Cache-Control": "no-store", "X-DACTE-Source": "xml"},
    )
