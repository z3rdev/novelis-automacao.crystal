import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MasterPolicy } from "@/routes/senha-mestre-dev";

const state = vi.hoisted(() => ({ enabled: true, configured: false, get: vi.fn(), save: vi.fn() }));
vi.mock("@/services", () => ({ useApi: () => ({ mode: "local", baseUrl: "fixture", api: {
  getDeveloperConfig: async () => ({ enabled: state.enabled }),
  getMasterPolicy: state.get, saveMasterPolicy: state.save,
} }) }));
beforeEach(() => {
  state.enabled = true; state.configured = false; vi.clearAllMocks();
  state.get.mockImplementation(async () => ({ configured: state.configured, updated_at: null, updated_by: null }));
  state.save.mockImplementation(async () => { state.configured = true; return { configured: true, updated_at: "2026-11-14T12:00:00Z", updated_by: "TEST\\operator" }; });
});
afterEach(cleanup);
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MasterPolicy /></QueryClientProvider>);
  return client;
}

it("permite cadastro e alteração apenas na tela do desenvolvedor, sem lembrar a senha", async () => {
  const client = mount();
  await screen.findByLabelText("Nova senha mestre");
  fireEvent.change(screen.getByLabelText("Nova senha mestre"), { target: { value: "test-only-password" } });
  fireEvent.change(screen.getByLabelText("Confirmar nova senha"), { target: { value: "different-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar senha mestre" }));
  expect(screen.getByRole("alert")).toHaveTextContent("As senhas não coincidem");
  expect(state.save).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Confirmar nova senha"), { target: { value: "test-only-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar senha mestre" }));
  await screen.findByRole("button", { name: "Alterar senha mestre" });
  expect(state.save).toHaveBeenCalledWith("test-only-password");
  expect(screen.getByLabelText("Nova senha mestre")).toHaveValue("");
  expect(screen.getByLabelText("Confirmar nova senha")).toHaveValue("");
  expect(JSON.stringify(client.getQueryData(["master-policy", "local", "fixture"]))).not.toContain("test-only-password");
  client.clear();
});

it("não consulta nem permite editar a política quando o modo desenvolvedor está desativado", async () => {
  state.enabled = false;
  const client = mount();
  await waitFor(() => expect(screen.getByText("Modo desenvolvedor desativado.")).toBeInTheDocument());
  expect(state.get).not.toHaveBeenCalled();
  expect(screen.queryByLabelText("Nova senha mestre")).not.toBeInTheDocument();
  expect(state.save).not.toHaveBeenCalled();
  client.clear();
});
