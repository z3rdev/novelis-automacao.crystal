import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { CteTariffPanel } from "./cte-tariff-panel";
import type { CteTariffAudit } from "@/services/cte-tariff";

afterEach(cleanup);
const audit: CteTariffAudit = {
  status: "divergente",
  origem: "PB-João Pessoa",
  destino: "PB-Cabedelo",
  dataReferencia: "2026-11-14",
  idObservacao: "217903",
  percursoObservacao: null,
  tonObservacao: "27",
  freteSql: "4644",
  outrosSql: "1200.83",
  frevalSql: "159.3",
  totalSql: "6004.13",
  totalReferencia: "6004.13",
  selecionada: {
    id: "952:666318",
    idTarifa: "666318",
    idRota: "952",
    origem: "PB-João Pessoa",
    destino: "PB-Cabedelo",
    tarifaTon: "154.80",
    valorTotal: "4644",
    capacidadeTon: "30",
    veiculo: "SIDER (30T)",
    operacao: "Matéria prima",
    faturamento: "",
    inicio: "2026-07-15",
    fim: "2026-12-31",
  },
  tonConfere: false,
  freteConfere: true,
  composicaoConfere: true,
  diferencaFrete: "0",
  diferencaTotal: "0",
  alertas: ["TON da observação diverge da referência."],
  candidatos: [],
  totalCandidatos: 1,
  catalogoAtualizadoEm: "2026-11-14T19:49:00Z",
  catalogoStatus: "completed",
};
it("distingue TON da observação e do tarifário e sinaliza sem bloquear", () => {
  render(<CteTariffPanel value={audit} />);
  expect(screen.getByText("Divergência")).toBeInTheDocument();
  const row = screen.getByRole("row", { name: /TON 27 t 30 t/ });
  expect(within(row).getByText("27 t")).toBeInTheDocument();
  expect(within(row).getByText("30 t")).toBeInTheDocument();
  expect(screen.getByText(/Tarifa 666318/)).toBeInTheDocument();
  expect(screen.getByText("217903")).toBeInTheDocument();
  expect(screen.getByText("Alertas não bloqueiam a abertura do chamado.")).toBeInTheDocument();
});
it("mostra a TON ausente sem apresentá-la como zero ou como conferida", () => {
  render(
    <CteTariffPanel
      value={{ ...audit, status: "dados_incompletos", tonObservacao: null, tonConfere: null }}
    />,
  );
  expect(screen.getByText("Não informada")).toBeInTheDocument();
  expect(screen.queryByText("0 t")).not.toBeInTheDocument();
});
