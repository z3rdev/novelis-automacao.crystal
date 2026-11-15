import { act, cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SidebarStatus } from "./sidebar-status";

const fixture = vi.hoisted(() => ({
  network: vi.fn(),
  ping: vi.fn().mockResolvedValue({ latenciaMs: 12 }),
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: { ping: fixture.ping }, mode: "local", baseUrl: "fixture" }),
}));
vi.mock("@/services/desktop", () => ({
  desktop: { isDesktop: true, networkStatus: fixture.network },
}));
vi.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => ({ state: "expanded", isMobile: false }),
}));
vi.mock("./session-gate", () => ({ useOperator: () => ({ session: null }) }));
vi.mock("./update-provider", () => ({ UpdateButton: () => null }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it("atualiza o ícone ao trocar a rede e mantém o indicador da API local", async () => {
  fixture.network.mockResolvedValue({ kind: "wifi", transport: null });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <SidebarStatus />
      </TooltipProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("img", { name: "Wi-Fi" })).toBeVisible();
  fixture.network.mockResolvedValue({ kind: "ethernet", transport: null });
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["desktop-network"] });
  });
  expect(await screen.findByRole("img", { name: "Rede cabeada" })).toBeVisible();
  fixture.network.mockResolvedValue({ kind: "vpn", transport: "ethernet" });
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["desktop-network"] });
  });
  expect(await screen.findByRole("img", { name: "VPN · Rede cabeada" })).toBeVisible();
  fixture.network.mockRejectedValue(new Error("probe_failed"));
  await act(async () => {
    await client.invalidateQueries({ queryKey: ["desktop-network"] });
  });
  expect(await screen.findByRole("img", { name: "Rede não identificada" })).toBeVisible();
  expect(screen.getByTestId("sidebar-status")).toHaveTextContent("Conectado · 12 ms");
  client.clear();
});
