from fastapi import APIRouter, Depends

from app.api.deps import get_mapping_repository
from app.domain.models import (
    RodoparFunctionGroup,
    RodoparMapCatalog,
    RodoparMapFunction,
    RodoparMapPoint,
    RodoparMapSubTab,
    RodoparMapTab,
)
from app.services.mapping_repository import MappingRepository


router = APIRouter(prefix="/mappings", tags=["mappings"])


@router.get("/rodopar", response_model=RodoparMapCatalog)
async def get_rodopar_mapping(
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapCatalog:
    return repository.list()


@router.put("/rodopar/points", response_model=RodoparMapPoint)
async def save_rodopar_point(
    point: RodoparMapPoint,
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapPoint:
    return repository.upsert_point(point)


@router.delete("/rodopar/points", response_model=RodoparMapCatalog)
async def delete_rodopar_point(
    tab: str,
    point_id: str,
    sub_tab: str = "",
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapCatalog:
    return repository.delete_point(tab, point_id, sub_tab)


@router.put("/rodopar/tabs", response_model=RodoparMapTab)
async def save_rodopar_tab(
    tab: RodoparMapTab,
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapTab:
    return repository.upsert_tab(tab)


@router.delete("/rodopar/tabs", response_model=RodoparMapCatalog)
async def delete_rodopar_tab(
    tab_id: str,
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapCatalog:
    return repository.delete_tab(tab_id)


@router.put("/rodopar/sub-tabs", response_model=RodoparMapSubTab)
async def save_rodopar_sub_tab(
    sub_tab: RodoparMapSubTab,
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapSubTab:
    return repository.upsert_sub_tab(sub_tab)


@router.delete("/rodopar/sub-tabs", response_model=RodoparMapCatalog)
async def delete_rodopar_sub_tab(
    tab: str,
    sub_tab_id: str,
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapCatalog:
    return repository.delete_sub_tab(tab, sub_tab_id)


@router.put("/rodopar/function-groups", response_model=RodoparFunctionGroup)
async def save_rodopar_function_group(
    group: RodoparFunctionGroup,
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparFunctionGroup:
    return repository.upsert_group(group)


@router.delete("/rodopar/function-groups", response_model=RodoparMapCatalog)
async def delete_rodopar_function_group(
    group_id: str,
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapCatalog:
    return repository.delete_group(group_id)


@router.put("/rodopar/functions", response_model=RodoparMapFunction)
async def save_rodopar_function(
    function: RodoparMapFunction,
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapFunction:
    return repository.upsert_function(function)


@router.delete("/rodopar/functions", response_model=RodoparMapCatalog)
async def delete_rodopar_function(
    function_id: str,
    repository: MappingRepository = Depends(get_mapping_repository),
) -> RodoparMapCatalog:
    return repository.delete_function(function_id)
