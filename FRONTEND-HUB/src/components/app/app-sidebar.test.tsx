import type { ComponentProps } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "./app-sidebar";

const fixtures = vi.hoisted(() => ({
  path: "/pendentes",
  developer: false,
  unread: 3,
  api: {
    getDeveloperConfig: vi.fn(),
    getOverview: vi.fn(),
    getRun: vi.fn(),
    getChamadosSummary: vi.fn(),
    ping: vi.fn(),
    listChamadosPage: vi.fn(),
  },
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: fixtures.api, mode: "local", baseUrl: "fixture" }),
}));
vi.mock("@tanstack/react-router", () => ({
  useRouterState: ({ select }: { select(state: unknown): unknown }) =>
    select({ location: { pathname: fixtures.path } }),
  Link: ({ to, children, ...props }: ComponentProps<"a"> & { to: string }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));
vi.mock("./notification-provider", () => ({
  useNotifications: () => ({ unread: fixtures.unread }),
}));
vi.mock("./update-provider", () => ({ UpdateButton: () => null }));

const clients: QueryClient[] = [];
beforeEach(() => {
  fixtures.path = "/pendentes";
  fixtures.developer = false;
  fixtures.unread = 3;
  vi.clearAllMocks();
  fixtures.api.getDeveloperConfig.mockImplementation(async () => ({ enabled: fixtures.developer }));
  fixtures.api.getOverview.mockResolvedValue({
    naFila: 12,
    ultimaAtualizacao: "2026-11-14T21:23:00Z",
  });
  fixtures.api.getRun.mockResolvedValue({ state: "executando" });
  fixtures.api.getChamadosSummary.mockResolvedValue({ counts: { em_analise: 264 } });
  fixtures.api.ping.mockResolvedValue({ latenciaMs: 22 });
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  vi.unstubAllGlobals();
});
function mount(collapsed = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const view = render(
    <QueryClientProvider client={client}>
      <SidebarProvider defaultOpen={!collapsed}>
        <AppSidebar />
      </SidebarProvider>
    </QueryClientProvider>,
  );
  return { ...view, client };
}

it("agrupa as tarefas e mostra contadores reais sem carregar as páginas do catálogo", async () => {
  mount();
  const pending = await screen.findByRole("link", {
    name: "CT-es pendentes · 12 ct-es sem chamado",
  });
  expect(pending).toHaveAttribute("aria-current", "page");
  expect(pending).toHaveAttribute("data-active", "true");
  expect(screen.getAllByRole("group").map((group) => group.getAttribute("aria-label"))).toEqual([
    "Automação",
    "Documentos fiscais",
    "Chamados Novelis",
    "Análise e cadastros",
  ]);
  expect(
    within(screen.getByRole("group", { name: "Chamados Novelis" })).getByRole("link", {
      name: "Modelo do chamado",
    }),
  ).toBeInTheDocument();
  await screen.findByRole("link", { name: "Chamados · 264 chamados em análise" });
  expect(screen.getByRole("img", { name: "Automação Executando" })).toBeInTheDocument();
  const footer = screen.getByRole("navigation", { name: "Ajuda e configurações" });
  expect(
    within(footer).getByRole("link", { name: "Notificações · 3 notificações não lidas" }),
  ).toBeInTheDocument();
  expect(screen.getByTestId("sidebar-status")).toHaveTextContent("Conectado · 22 ms");
  expect(fixtures.api.listChamadosPage).not.toHaveBeenCalled();
});

it("mantém as opções de desenvolvimento dentro de Configurações e respeita sua habilitação", async () => {
  const { client } = mount();
  await waitFor(() =>
    expect(client.getQueryData(["developer-config", "local", "fixture"])).toEqual({
      enabled: false,
    }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Configurações" }));
  expect(screen.getByRole("link", { name: "Geral e diagnóstico" })).toHaveAttribute(
    "href",
    "/configuracoes",
  );
  expect(screen.queryByRole("link", { name: "Segurança" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Avançado" })).not.toBeInTheDocument();
  fixtures.developer = true;
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["developer-config"] });
  });
  expect(await screen.findByRole("link", { name: "Usuários e dispositivos" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Segurança" })).toHaveAttribute(
    "href",
    "/senha-mestre-dev",
  );
  expect(screen.getByRole("link", { name: "Publicar notificações" })).toHaveAttribute(
    "href",
    "/notificacoes-dev",
  );
  expect(screen.queryByText("Desenvolvimento")).not.toBeInTheDocument();
});

it("busca páginas e grupos sem exigir acentos e abre os subitens encontrados", async () => {
  fixtures.developer = true;
  mount();
  await waitFor(() => expect(fixtures.api.getDeveloperConfig).toHaveBeenCalled());
  fireEvent.change(screen.getByRole("textbox", { name: "Buscar no menu" }), {
    target: { value: "seguranca" },
  });
  expect(await screen.findByRole("link", { name: "Segurança" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Visão geral" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "Buscar no menu" }), {
    target: { value: "documentos fiscais" },
  });
  expect(screen.getByRole("group", { name: "Documentos fiscais" })).toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "Automação" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "Buscar no menu" }), {
    target: { value: "inexistente" },
  });
  expect(screen.getByText("Nenhuma página encontrada.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Limpar busca do menu" }));
  expect(screen.getByRole("link", { name: "Visão geral" })).toBeInTheDocument();
});

it("oferece Configurações em menu flutuante quando a barra está recolhida", async () => {
  mount(true);
  const button = screen.getByRole("button", { name: "Configurações" });
  fireEvent.keyDown(button, { key: "Enter" });
  expect(await screen.findByRole("menuitem", { name: "Geral e diagnóstico" })).toHaveAttribute(
    "href",
    "/configuracoes",
  );
});

it("reabre a barra de ícones pela busca e não apresenta zero ao falhar uma contagem", async () => {
  fixtures.api.getChamadosSummary.mockRejectedValue(new Error("Indisponível"));
  mount(true);
  fireEvent.click(screen.getByRole("button", { name: "Buscar no menu" }));
  expect(screen.getByRole("textbox", { name: "Buscar no menu" })).toBeInTheDocument();
  expect(await screen.findByRole("link", { name: "Chamados" })).not.toHaveTextContent("0");
});

it("deixa a busca da Ajuda como única busca quando essa página está aberta", () => {
  fixtures.path = "/ajuda";
  mount();
  expect(screen.queryByRole("textbox", { name: "Buscar no menu" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Ajuda" })).toHaveAttribute("aria-current", "page");
});
