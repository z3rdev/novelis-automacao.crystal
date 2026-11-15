export type TariffValidity = "vigente" | "vencida" | "futura" | "inconsistente";
export interface TariffCity {
  portal_id: string;
  ibge: number | null;
  label: string;
  portal_label: string;
  matched: boolean;
}
export interface Tariff {
  id: string;
  idTarifa: string;
  idRota: string;
  origem: string;
  destino: string;
  origemPortal: string;
  destinoPortal: string;
  origemId: string;
  destinoId: string;
  origemIbge: number | null;
  destinoIbge: number | null;
  operacao: string;
  transportadora: string;
  faturamento: string;
  grupoEmpresa: string;
  ramo: string;
  tipoTransporte: string;
  veiculo: string;
  outrosCustos: string;
  ranking: string;
  share: string;
  tarifaTon: string | null;
  valorTotal: string | null;
  capacidadeTon: string | null;
  adValorem: string | null;
  inicio: string | null;
  fim: string | null;
  inicioPortal: string;
  fimPortal: string;
  vigenciaValida: boolean;
  status: TariffValidity;
  presentePortal: boolean;
  conferidoEm: string;
}
export interface TariffSync {
  stage?: string;
  error_code?: string;
  state: string;
  started_at: string | null;
  completed_at: string | null;
  next_check_at: string | null;
  message: string;
  total: number;
  cities: number;
  unmatched: number;
}
export interface TariffQuery {
  search?: string;
  origin?: string;
  destination?: string;
  vehicle?: string;
  validity?: TariffValidity | "todos";
  page?: number;
  size?: number;
}
export interface TariffPage {
  rows: Tariff[];
  total: number;
  page: number;
  page_size: number;
  counts: Partial<Record<TariffValidity, number>>;
  vehicles: string[];
  sync: TariffSync;
}
export interface TariffEstimate {
  idTarifa: string;
  toneladas: string;
  tarifaTon: string;
  valor: string;
  status: TariffValidity;
  excedeCapacidade: boolean;
  presentePortal: boolean;
}
export interface TariffApi {
  listTariffs(query: TariffQuery): Promise<TariffPage>;
  tariffCities(search: string): Promise<TariffCity[]>;
  getTariffSync(): Promise<TariffSync>;
  refreshTariffs(): Promise<TariffSync>;
  estimateTariff(id: string, tonnes: string): Promise<TariffEstimate>;
}
export const tariffLabels: Record<TariffValidity, string> = {
  vigente: "Vigente",
  vencida: "Vencida",
  futura: "Futura",
  inconsistente: "Conferir vigência",
};
export const tariffTones: Record<TariffValidity, string> = {
  vigente: "border-success/30 bg-success/10 text-success",
  vencida: "border-border bg-muted text-muted-foreground",
  futura: "border-info/30 bg-info/10 text-info",
  inconsistente: "border-warning/40 bg-warning/10 text-warning-foreground",
};
