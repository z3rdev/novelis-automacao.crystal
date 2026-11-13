import type { RodoparMapCatalog, RodoparMapPoint } from "../../lib/api";

export const DEFAULT_RODOPAR_TABS = [
  "Geral",
  "Adicionais",
  "Comp. Carga",
  "Comp. do Frete",
  "Retornaveis",
  "Logs",
  "Complementares",
  "Texto Adicional",
  "Anexo",
  "Aduanas/Despachantes",
];

export function toMapId(value: string) {
  return value
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
}

export function sameMapName(left = "", right = "") {
  return left === right || toMapId(left) === toMapId(right);
}

export function sameMapScope(
  itemTab: string,
  itemSubTab: string | undefined,
  selectedTab: string,
  selectedSubTab: string,
) {
  return sameMapName(itemTab, selectedTab) && sameMapName(itemSubTab || "", selectedSubTab);
}

export function emptyMappingCatalog(): RodoparMapCatalog {
  return {
    source: "rodopar-preview",
    updated_at: "",
    tabs: [],
    sub_tabs: [],
    points: [],
    function_groups: [],
    functions: [],
  };
}

export function mapPointKey(point: RodoparMapPoint) {
  return `${point.tab}:${point.sub_tab ?? ""}:${point.id}`;
}
