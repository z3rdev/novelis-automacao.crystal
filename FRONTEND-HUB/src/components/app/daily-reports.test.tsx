import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Reports } from "@/routes/relatorios";
import { selectOption } from "@/test/select-option";

const mocks = vi.hoisted(() => ({
  api: {
    listExecutionReports: vi.fn(),
    getExecutionReport: vi.fn(),
    downloadExecutionReport: vi.fn(),
    syncExecutionReports: vi.fn(),
  },
  saveFile: vi.fn(),
  openPath: vi.fn(),
}));

vi.mock("@/services", () => ({
  useApi: () => ({ api: mocks.api, mode: "local", baseUrl: "test" }),
}));
vi.mock("@tanstack/react-router", () => ({ createFileRoute: () => () => ({}) }));
vi.mock("@/services/desktop", () => ({
  desktop: { saveFile: mocks.saveFile, openPath: mocks.openPath },
}));

const report = {
  id: "daily-14",
  kind: "daily",
  report_date: "2026-11-14",
  operator: "Ana, Bruno",
  opened_count: 2,
  run_count: 2,
  generated_at: "2026-11-15T00:00:00Z",
  share_status: "shared",
  share_message: "Disponível no MinIO.",
  opened: [
    {
      cte: "8-10-101",
      numero: "1001",
      link: "https://novelis.wtmh.com.br/portal/chamado/1001",
      operator: "Ana",
      computer: "PC-A",
      ton: "30",
      origem: "João Pessoa",
      destino: "Cabedelo",
      valor: 100,
      confirmado_em: "2026-11-14T20:00:00-03:00",
    },
    {
      cte: "8-10-102",
      numero: "1002",
      link: "https://novelis.wtmh.com.br/portal/chamado/1002",
      operator: "Bruno",
      computer: "PC-B",
      ton: "30",
      origem: "João Pessoa",
      destino: "Cabedelo",
      valor: 200,
      confirmado_em: "2026-11-14T21:00:00-03:00",
    },
  ],
};

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Reports />
    </QueryClientProvider>,
  );
  return client;
}

describe("Daily execution reports", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.api.listExecutionReports.mockResolvedValue({
      rows: [report],
      total: 1,
      page: 0,
      page_size: 30,
    });
    mocks.api.getExecutionReport.mockResolvedValue(report);
    mocks.api.downloadExecutionReport.mockResolvedValue(new Blob(["excel"]));
  });
  afterEach(cleanup);

  it("shows one date and saves an Excel named by date", async () => {
    const client = mount();
    expect(await screen.findByText("14/11/2026")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Relatórios diários" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Baixar Excel 14/11/2026" }));
    await waitFor(() =>
      expect(mocks.saveFile).toHaveBeenCalledWith(
        "CargoHub-Chamados-2026-11-14.xlsx",
        expect.any(Blob),
      ),
    );
    client.clear();
  });

  it("opens a side panel with all confirmed tickets and their operators", async () => {
    const client = mount();
    fireEvent.click(await screen.findByText("14/11/2026"));
    expect(await screen.findByRole("heading", { name: "Chamados do dia" })).toBeInTheDocument();
    expect(await screen.findByText("8-10-101")).toBeInTheDocument();
    expect(screen.getByText("8-10-102")).toBeInTheDocument();
    expect(screen.getByText("PC-A")).toBeInTheDocument();
    expect(screen.getByText("PC-B")).toBeInTheDocument();
    expect(mocks.api.getExecutionReport).toHaveBeenCalledWith("daily-14");
    client.clear();
  });

  it("starts with recent tickets and filters locally without changing the full Excel download", async () => {
    const client = mount();
    fireEvent.click(await screen.findByText("14/11/2026"));
    const list = await screen.findByRole("list", { name: "Chamados abertos" });
    await screen.findByRole("article", { name: "CT-e 8-10-102" });
    expect(within(list).getAllByRole("article")[0]).toHaveAccessibleName("CT-e 8-10-102");
    await selectOption("Ordenar chamados do dia", "Mais antigos");
    expect(within(list).getAllByRole("article")[0]).toHaveAccessibleName("CT-e 8-10-101");
    fireEvent.change(screen.getByLabelText("Buscar chamados do dia"), { target: { value: "Ana" } });
    expect(within(list).getAllByRole("article")).toHaveLength(1);
    expect(screen.queryByRole("article", { name: "CT-e 8-10-102" })).toBeNull();
    expect(screen.getByText("1 de 2 chamados")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Baixar Excel" }));
    await waitFor(() => expect(mocks.api.downloadExecutionReport).toHaveBeenCalledWith("daily-14"));
    client.clear();
  });

  it("searches routes without accents, clears an empty search and opens the correct ticket", async () => {
    const client = mount();
    fireEvent.click(await screen.findByText("14/11/2026"));
    await screen.findByRole("article", { name: "CT-e 8-10-101" });
    const search = screen.getByLabelText("Buscar chamados do dia");
    fireEvent.change(search, { target: { value: "joao pessoa" } });
    expect(screen.getAllByRole("article")).toHaveLength(2);
    fireEvent.change(search, { target: { value: "nenhum" } });
    expect(screen.getByText("Nenhum chamado corresponde à busca.")).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: "Limpar busca" })[0]!);
    fireEvent.click(screen.getByRole("button", { name: "Abrir chamado 1001" }));
    expect(mocks.openPath).toHaveBeenCalledWith("https://novelis.wtmh.com.br/portal/chamado/1001");
    client.clear();
  });
});
