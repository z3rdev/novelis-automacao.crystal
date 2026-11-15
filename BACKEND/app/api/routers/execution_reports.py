import asyncio
import sqlite3
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from app.api.deps import require_operator_session

router = APIRouter(
    prefix="/hub/execution-reports",
    tags=["execution-reports"],
    dependencies=[Depends(require_operator_session)],
)


def service(request):
    value = getattr(request.app.state, "execution_reports", None)
    if not value:
        raise HTTPException(503, "Relatórios compartilhados indisponíveis.")
    return value


async def invoke(action, *args):
    try:
        return await asyncio.to_thread(action, *args)
    except LookupError:
        raise HTTPException(404, "Relatório não encontrado.") from None
    except (RuntimeError, OSError, sqlite3.Error):
        raise HTTPException(
            503, "Relatório indisponível. Verifique o MinIO e a pasta compartilhada."
        ) from None


@router.get("")
async def reports(request: Request, page: int = Query(0, ge=0)):
    return await invoke(service(request).page, page)


@router.post("/sync", status_code=202)
async def sync(request: Request):
    service(request).sync()
    return {"status": "pending"}


@router.get("/{run_id}")
async def detail(run_id: UUID, request: Request):
    return await invoke(service(request).detail, str(run_id))


@router.get("/{run_id}/file")
async def file(run_id: UUID, request: Request):
    path = await invoke(service(request).download, str(run_id))
    return FileResponse(
        path,
        filename=f"CargoHub-Chamados-{path.stem if path.parent.name == 'daily' else str(run_id)[:8]}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Cache-Control": "no-store"},
    )
