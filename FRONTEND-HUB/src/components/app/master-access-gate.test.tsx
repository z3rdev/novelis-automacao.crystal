import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MasterAccessGate } from "./master-access-gate";
import type { ReactNode } from "react";
vi.mock("@tanstack/react-router", () => ({ Link: ({to,children}: {to:string;children?:ReactNode}) => <a href={to}>{children}</a> }));

const state = vi.hoisted(() => ({ configured: true, can_setup: false, unlocked: false, setup: vi.fn(), unlock: vi.fn(), lock: vi.fn(), child: vi.fn() }));
vi.mock("@/services", () => ({ useApi: () => ({ mode: "local", baseUrl: "fixture", api: {
  getMasterAccess: async () => ({ configured: state.configured, can_setup: state.can_setup, unlocked: state.unlocked, expires_at: null }),
  setupMasterAccess: state.setup, unlockMasterAccess: state.unlock, lockMasterAccess: state.lock,
} }) }));
vi.mock("./session-gate", () => ({ useOperator: () => ({ session: { id: "fixture-session" } }) }));
function PrivateContent() { state.child(); return <p>Conteúdo reservado</p>; }
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MasterAccessGate><PrivateContent /></MasterAccessGate></QueryClientProvider>);
  return client;
}
beforeEach(() => { state.configured = true; state.can_setup = false; state.unlocked = false; vi.clearAllMocks(); });
afterEach(cleanup);

it("não monta as configurações antes da confirmação do backend e bloqueia novamente", async () => {
  state.unlock.mockImplementation(async () => { state.unlocked = true; return { configured: true, can_setup: false, unlocked: true, expires_at: null }; });
  state.lock.mockImplementation(async () => { state.unlocked = false; });
  const client = mount();
  await screen.findByLabelText("Senha mestre");
  expect(state.child).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Senha mestre"), { target: { value: "test-only-passphrase" } });
  fireEvent.click(screen.getByRole("button", { name: /Desbloquear configurações/ }));
  await screen.findByText("Conteúdo reservado");
  expect(state.unlock).toHaveBeenCalledWith("test-only-passphrase");
  fireEvent.click(screen.getByRole("button", { name: "Bloquear" }));
  await waitFor(() => expect(screen.queryByText("Conteúdo reservado")).not.toBeInTheDocument());
  expect(screen.getByLabelText("Senha mestre")).toHaveValue("");
  client.clear();
});

it("mantém acesso fechado para senha incorreta e direciona o cadastro à tela de desenvolvedor", async () => {
  state.unlock.mockRejectedValue(new Error("Senha mestre incorreta."));
  const client = mount();
  await screen.findByLabelText("Senha mestre");
  fireEvent.change(screen.getByLabelText("Senha mestre"), { target: { value: "test-wrong-password" } });
  fireEvent.click(screen.getByRole("button", { name: /Desbloquear configurações/ }));
  await screen.findByRole("alert");
  expect(state.child).not.toHaveBeenCalled();
  client.clear(); cleanup();
  state.configured = false; state.can_setup = true;
  const next = mount();
  await screen.findByRole("link", { name: "Gerenciar senha mestre" });
  expect(screen.getByRole("link")).toHaveAttribute("href", "/senha-mestre-dev");
  expect(screen.queryByLabelText("Nova senha mestre")).not.toBeInTheDocument();
  expect(state.setup).not.toHaveBeenCalled();
  next.clear();
});
