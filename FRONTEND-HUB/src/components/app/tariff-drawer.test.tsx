import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { TariffDrawer } from "./tariff-drawer";
import { exampleTariff } from "@/services/tariff-mock";

const state = vi.hoisted(() => ({ estimate: vi.fn() }));
vi.mock("@/services", () => ({
  useApi: () => ({ mode: "local", api: { estimateTariff: state.estimate } }),
}));
afterEach(cleanup);
it("calcula com a tonelagem informada sem preencher a capacidade do veículo como carga", async () => {
  state.estimate.mockResolvedValue({
    idTarifa: "3113",
    toneladas: "27.5",
    tarifaTon: "424.00",
    valor: "11660.00",
    status: "vigente",
    excedeCapacidade: false,
    presentePortal: true,
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TariffDrawer value={exampleTariff} onClose={() => {}} />
    </QueryClientProvider>,
  );
  expect(screen.getByLabelText("Toneladas da carga")).toHaveValue("");
  expect(screen.getByText("36 t")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Toneladas da carga"), { target: { value: "27,5" } });
  fireEvent.click(screen.getByRole("button", { name: "Calcular" }));
  await waitFor(() => expect(state.estimate).toHaveBeenCalledWith("demo", "27,5"));
  expect(await screen.findByText(/11.660,00/)).toBeInTheDocument();
  expect(screen.getByText(/27.5 t/)).toBeInTheDocument();
  client.clear();
});
