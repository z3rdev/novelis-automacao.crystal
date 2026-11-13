from pathlib import Path

from app.domain.models import (
    RodoparFunctionGroup,
    RodoparMapCatalog,
    RodoparMapFunction,
    RodoparMapPoint,
    RodoparMapSubTab,
    RodoparMapTab,
    utc_now,
)
from app.infrastructure.json_store import read_json, write_json


class MappingRepository:
    def __init__(self, mapping_file: Path) -> None:
        self.mapping_file = mapping_file

    def list(self) -> RodoparMapCatalog:
        payload = read_json(
            self.mapping_file,
            {"source": "rodopar-preview", "tabs": [], "sub_tabs": [], "points": []},
        )
        return RodoparMapCatalog.model_validate(payload)

    def upsert_point(self, point: RodoparMapPoint) -> RodoparMapPoint:
        catalog = self.list()
        normalized = point.model_copy(update={"updated_at": utc_now()})
        points = [
            existing
            for existing in catalog.points
            if not self._same_key(existing, normalized)
        ]
        points.append(normalized)
        catalog.points = sorted(
            points,
            key=lambda item: (item.tab.lower(), item.sub_tab.lower(), item.id.lower()),
        )
        catalog.updated_at = utc_now()
        write_json(self.mapping_file, catalog.model_dump(mode="json"))
        return normalized

    def delete_point(self, tab: str, point_id: str, sub_tab: str = "") -> RodoparMapCatalog:
        catalog = self.list()
        catalog.points = [
            point
            for point in catalog.points
            if not self._same_point_values(point, tab, sub_tab, point_id)
        ]
        catalog.updated_at = utc_now()
        write_json(self.mapping_file, catalog.model_dump(mode="json"))
        return catalog

    def upsert_tab(self, tab: RodoparMapTab) -> RodoparMapTab:
        catalog = self.list()
        normalized = tab.model_copy(update={"updated_at": utc_now()})
        catalog.tabs = [
            existing for existing in catalog.tabs if existing.id.lower() != normalized.id.lower()
        ]
        catalog.tabs.append(normalized)
        catalog.tabs = sorted(catalog.tabs, key=lambda item: (item.order, item.name.lower()))
        self._write(catalog)
        return normalized

    def delete_tab(self, tab_id: str) -> RodoparMapCatalog:
        catalog = self.list()
        catalog.tabs = [tab for tab in catalog.tabs if tab.id.lower() != tab_id.lower()]
        catalog.sub_tabs = [sub for sub in catalog.sub_tabs if sub.tab.lower() != tab_id.lower()]
        self._write(catalog)
        return catalog

    def upsert_sub_tab(self, sub_tab: RodoparMapSubTab) -> RodoparMapSubTab:
        catalog = self.list()
        normalized = sub_tab.model_copy(update={"updated_at": utc_now()})
        catalog.sub_tabs = [
            existing
            for existing in catalog.sub_tabs
            if not self._same_sub_tab(existing, normalized)
        ]
        catalog.sub_tabs.append(normalized)
        catalog.sub_tabs = sorted(
            catalog.sub_tabs,
            key=lambda item: (item.tab.lower(), item.order, item.name.lower()),
        )
        self._write(catalog)
        return normalized

    def delete_sub_tab(self, tab: str, sub_tab_id: str) -> RodoparMapCatalog:
        catalog = self.list()
        catalog.sub_tabs = [
            item
            for item in catalog.sub_tabs
            if item.tab.lower() != tab.lower() or item.id.lower() != sub_tab_id.lower()
        ]
        catalog.points = [
            point.model_copy(update={"sub_tab": ""})
            if point.tab.lower() == tab.lower() and point.sub_tab.lower() == sub_tab_id.lower()
            else point
            for point in catalog.points
        ]
        catalog.function_groups = [
            group.model_copy(update={"sub_tab": ""})
            if group.tab.lower() == tab.lower() and group.sub_tab.lower() == sub_tab_id.lower()
            else group
            for group in catalog.function_groups
        ]
        catalog.functions = [
            function.model_copy(update={"sub_tab": ""})
            if function.tab.lower() == tab.lower() and function.sub_tab.lower() == sub_tab_id.lower()
            else function
            for function in catalog.functions
        ]
        self._write(catalog)
        return catalog

    def upsert_group(self, group: RodoparFunctionGroup) -> RodoparFunctionGroup:
        catalog = self.list()
        normalized = group.model_copy(update={"updated_at": utc_now()})
        catalog.function_groups = [
            existing
            for existing in catalog.function_groups
            if existing.id.lower() != normalized.id.lower()
        ]
        catalog.function_groups.append(normalized)
        catalog.function_groups = sorted(
            catalog.function_groups,
            key=lambda item: (item.tab.lower(), item.sub_tab.lower(), item.order, item.name.lower()),
        )
        self._write(catalog)
        return normalized

    def delete_group(self, group_id: str) -> RodoparMapCatalog:
        catalog = self.list()
        catalog.function_groups = [
            group for group in catalog.function_groups if group.id.lower() != group_id.lower()
        ]
        catalog.functions = [
            function.model_copy(update={"group_id": ""})
            if function.group_id.lower() == group_id.lower()
            else function
            for function in catalog.functions
        ]
        self._write(catalog)
        return catalog

    def upsert_function(self, function: RodoparMapFunction) -> RodoparMapFunction:
        catalog = self.list()
        normalized = function.model_copy(update={"updated_at": utc_now()})
        catalog.functions = [
            existing
            for existing in catalog.functions
            if existing.id.lower() != normalized.id.lower()
        ]
        catalog.functions.append(normalized)
        catalog.functions = sorted(
            catalog.functions,
            key=lambda item: (
                item.tab.lower(),
                item.sub_tab.lower(),
                item.group_id.lower(),
                item.id.lower(),
            ),
        )
        self._write(catalog)
        return normalized

    def delete_function(self, function_id: str) -> RodoparMapCatalog:
        catalog = self.list()
        catalog.functions = [
            function
            for function in catalog.functions
            if function.id.lower() != function_id.lower()
        ]
        self._write(catalog)
        return catalog

    def _write(self, catalog: RodoparMapCatalog) -> None:
        catalog.updated_at = utc_now()
        write_json(self.mapping_file, catalog.model_dump(mode="json"))

    @staticmethod
    def _same_key(left: RodoparMapPoint, right: RodoparMapPoint) -> bool:
        return (
            left.tab.lower() == right.tab.lower()
            and left.sub_tab.lower() == right.sub_tab.lower()
            and left.id.lower() == right.id.lower()
        )

    @staticmethod
    def _same_point_values(
        point: RodoparMapPoint,
        tab: str,
        sub_tab: str,
        point_id: str,
    ) -> bool:
        return (
            point.tab.lower() == tab.lower()
            and point.sub_tab.lower() == sub_tab.lower()
            and point.id.lower() == point_id.lower()
        )

    @staticmethod
    def _same_sub_tab(left: RodoparMapSubTab, right: RodoparMapSubTab) -> bool:
        return left.tab.lower() == right.tab.lower() and left.id.lower() == right.id.lower()
