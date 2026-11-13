from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_repository
from app.domain.models import StepCatalog, StepDefinition, StepPatch
from app.services.step_repository import StepRepository


router = APIRouter(prefix="/steps", tags=["steps"])


@router.get("", response_model=StepCatalog)
async def list_steps(repository: StepRepository = Depends(get_repository)) -> StepCatalog:
    return repository.list()


@router.get("/{number}", response_model=StepDefinition)
async def get_step(
    number: int,
    repository: StepRepository = Depends(get_repository),
) -> StepDefinition:
    try:
        return repository.get(number)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{number}", response_model=StepDefinition)
async def update_step(
    number: int,
    patch: StepPatch,
    repository: StepRepository = Depends(get_repository),
) -> StepDefinition:
    try:
        return repository.update(number, patch)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
