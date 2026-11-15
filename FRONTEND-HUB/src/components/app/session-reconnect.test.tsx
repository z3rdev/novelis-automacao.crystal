import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { SessionGate } from "./session-gate";

const state = vi.hoisted(() => ({ getSession: vi.fn() }));
vi.mock("@/services", () => ({
  useApi: () => ({
    mode: "local",
    baseUrl: "fixture",
    setMode: vi.fn(),
    api: { getSession: state.getSession },
  }),
}));
vi.mock("@/services/desktop", () => ({
  desktop: {
    isDesktop: true,
    deviceIdentity: async () => ({
      windows_user: "TEST\\operator",
      computer_name: "TEST-NATIVE-PC",
      mac_addresses: ["02:00:00:00:00:01"],
    }),
  },
}));
afterEach(cleanup);
it("identifica o dispositivo sem backend e tenta reconectar automaticamente", async () => {
  state.getSession.mockRejectedValueOnce(new Error("offline")).mockResolvedValue({
    identity: {
      windows_user: "TEST\\operator",
      computer_name: "TEST-NATIVE-PC",
      mac_addresses: [],
    },
    session: null,
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SessionGate>
        <p>Área de trabalho</p>
      </SessionGate>
    </QueryClientProvider>,
  );
  await screen.findAllByText("TEST-NATIVE-PC");
  await screen.findByText("Aguardando o backend local");
  expect(screen.queryByRole("button", { name: "Tentar novamente" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Aguardando conexão/ })).toBeDisabled();
  await waitFor(
    () => expect(screen.getByRole("button", { name: /Entrar no Cargo Hub/ })).toBeEnabled(),
    { timeout: 8000 },
  );
  expect(state.getSession).toHaveBeenCalledTimes(2);
  expect(screen.getByLabelText("Nome do operador")).toHaveValue("operator");
  expect(screen.getByLabelText("Nome do operador")).toHaveAttribute("readonly");
  client.clear();
}, 15000);
