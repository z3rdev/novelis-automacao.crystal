import type { TariffApi, Tariff, TariffSync } from "./tariffs";
const sync: TariffSync = {
  state: "completed",
  started_at: null,
  completed_at: null,
  next_check_at: null,
  message: "Dados de demonstração",
  total: 1,
  cities: 2,
  unmatched: 0,
};
export const exampleTariff: Tariff = {
  id: "demo",
  idTarifa: "3113",
  idRota: "306",
  origem: "SP-Pindamonhangaba",
  destino: "ES-Cariacica",
  origemPortal: "SP-Pindamonhangaba",
  destinoPortal: "ES-Cariacica",
  origemId: "3791",
  destinoId: "1112",
  origemIbge: 3538006,
  destinoIbge: 3201308,
  operacao: "Transferência",
  transportadora: "Transportadora de exemplo",
  faturamento: "",
  grupoEmpresa: "",
  ramo: "OUTBOUND",
  tipoTransporte: "RODOVIARIO",
  veiculo: "SIDER (36T)",
  outrosCustos: "",
  ranking: "2",
  share: "0",
  tarifaTon: "424.00",
  valorTotal: "15264.00",
  capacidadeTon: "36",
  adValorem: "0",
  inicio: "2026-11-01",
  fim: "2026-11-30",
  inicioPortal: "01/11/2026",
  fimPortal: "30/11/2026",
  vigenciaValida: true,
  status: "vigente",
  presentePortal: true,
  conferidoEm: "2026-11-14T12:00:00Z",
};
export const tariffMock: TariffApi = {
  async listTariffs(q) {
    const rows =
      (!q.validity || q.validity === "todos" || q.validity === "vigente") &&
      (!q.origin || q.origin === exampleTariff.origemId) &&
      (!q.destination || q.destination === exampleTariff.destinoId) &&
      (!q.vehicle || q.vehicle === exampleTariff.veiculo) &&
      (!q.search || JSON.stringify(exampleTariff).toLowerCase().includes(q.search.toLowerCase()))
        ? [exampleTariff]
        : [];
    return {
      rows,
      total: rows.length,
      page: 0,
      page_size: 50,
      counts: { vigente: 1 },
      vehicles: [exampleTariff.veiculo],
      sync,
    };
  },
  async tariffCities(search) {
    return [
      {
        portal_id: "3791",
        ibge: 3538006,
        label: "SP-Pindamonhangaba",
        portal_label: "SP-Pindamonhangaba",
        matched: true,
      },
      {
        portal_id: "1112",
        ibge: 3201308,
        label: "ES-Cariacica",
        portal_label: "ES-Cariacica",
        matched: true,
      },
    ].filter((c) => c.label.toLowerCase().includes(search.toLowerCase()));
  },
  async getTariffSync() {
    return sync;
  },
  async refreshTariffs() {
    throw new Error("Atualização disponível no backend local.");
  },
  async estimateTariff(_, tonnes) {
    const weight = Number(tonnes.replace(",", "."));
    if (!Number.isFinite(weight) || weight <= 0) throw new Error("Informe uma tonelagem válida.");
    return {
      idTarifa: exampleTariff.idTarifa,
      toneladas: String(weight),
      tarifaTon: "424.00",
      valor: (weight * 424).toFixed(2),
      status: "vigente",
      excedeCapacidade: weight > 36,
      presentePortal: true,
    };
  },
};
