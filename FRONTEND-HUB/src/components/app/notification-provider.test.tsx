import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { HubNotification } from "@/services/types";
import { AppDialogs } from "./app-dialogs";
import { NotificationProvider, NotificationBell } from "./notification-provider";
import type { ReactNode } from "react";

vi.mock("@tanstack/react-router", () => ({ Link: ({ to, children, ...props }: { to: string; children?: ReactNode }) => <a href={to} {...props}>{children}</a> }));

const state = vi.hoisted(() => ({ items: [] as HubNotification[], read: vi.fn() }));
vi.mock("@/services", () => ({ useApi: () => ({ mode: "local", baseUrl: "fixture-api", api: {
  getNotifications: async () => structuredClone(state.items),
  markNotificationRead: async (id: string) => {
    state.read(id);
    state.items = state.items.map((item) => item.id === id ? { ...item, read_at: new Date().toISOString() } : item);
  },
} }) }));
vi.mock("./session-gate", () => ({ useOperator: () => ({ session: { id: "fixture-session", windows_user: "TEST\\operator" } }) }));
const notice = (id: string): HubNotification => ({ id, title: `Aviso ${id}`, body: `Mensagem ${id}`, severity: "info", author: "Equipe", created_at: "2026-11-14T12:00:00Z", archived_at: null, expires_at: null, read_at: null });
const mount = (inboxOpen = false) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><AppDialogs><NotificationProvider inboxOpen={inboxOpen}><NotificationBell /></NotificationProvider></AppDialogs></QueryClientProvider>);
  return client;
};
beforeEach(() => { state.items = []; state.read.mockClear(); });
afterEach(cleanup);

describe("Novos comunicados", () => {
  it("abre automaticamente para um aviso recebido depois de fechar o anterior, sem marcá-lo na abertura", async () => {
    state.items = [notice("um")];
    const client = mount();
    await screen.findByRole("dialog");
    expect(state.read).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Fechar" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    state.items = [notice("dois"), ...state.items];
    await act(async () => { await client.invalidateQueries({ queryKey: ["notifications"] }); });
    await screen.findByRole("dialog");
    expect(screen.getByText("Mensagem dois")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Marcar como lida" }));
    await waitFor(() => expect(state.read).toHaveBeenCalledWith("dois"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Mensagem lida" })).toBeDisabled());
    expect(state.read).not.toHaveBeenCalledWith("um");
    client.clear();
  });

  it("marca todas as não lidas e atualiza o indicador", async () => {
    state.items = [notice("primeiro"), notice("segundo")];
    const client = mount();
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: "Marcar todas como lidas" }));
    await waitFor(() => expect(state.read).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByRole("button", { name: "Mensagem lida" })).toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "Fechar" }));
    await waitFor(() => expect(screen.getByRole("link", { name: "Notificações" })).toHaveAttribute("href", "/notificacoes"));
    expect(state.items.every((item) => item.read_at)).toBe(true);
    client.clear();
  });

  it("abre a página pelo link do cabeçalho e não sobrepõe um modal à caixa de entrada", async () => {
    state.items = [notice("novo")];
    const client = mount(true);
    await screen.findByRole("link", { name: "Notificações, 1 não lidas" });
    expect(screen.getByRole("link")).toHaveAttribute("href", "/notificacoes");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(state.read).not.toHaveBeenCalled();
    client.clear();
  });
});
