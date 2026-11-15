import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { desktop } from "@/services/desktop";
import { DesktopSettings } from "./desktop-settings";

vi.mock("@/services/desktop", () => ({
  desktop: {
    isDesktop: true,
    startupEnabled: vi.fn(),
    setStartup: vi.fn(),
    hideToTray: vi.fn(),
    widgetEnabled: vi.fn(),
    setWidgetEnabled: vi.fn(),
    showStatusWidget: vi.fn(),
  },
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
beforeEach(() => {
  desktop.isDesktop = true;
  vi.mocked(desktop.startupEnabled).mockResolvedValue(false);
  vi.mocked(desktop.setStartup).mockImplementation(async (value) => value);
  vi.mocked(desktop.hideToTray).mockResolvedValue(undefined);
  vi.mocked(desktop.widgetEnabled).mockResolvedValue(true);
  vi.mocked(desktop.setWidgetEnabled).mockImplementation(async (value) => value);
  vi.mocked(desktop.showStatusWidget).mockResolvedValue(undefined);
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
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

function show() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <DesktopSettings />
    </QueryClientProvider>,
  );
}

describe("preferências do aplicativo nativo", () => {
  it("consulta a inicialização e altera somente após a ação do operador", async () => {
    show();
    const toggle = screen.getByRole("switch", { name: "Iniciar com o Windows" });
    await waitFor(() => expect(toggle).toBeEnabled());
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(desktop.setStartup).not.toHaveBeenCalled();
    fireEvent.click(toggle);
    await waitFor(() => expect(desktop.setStartup).toHaveBeenCalledExactlyOnceWith(true));
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));
  });
  it("oculta a janela pela integração nativa", async () => {
    show();
    fireEvent.click(screen.getByRole("button", { name: "Manter em segundo plano" }));
    await waitFor(() => expect(desktop.hideToTray).toHaveBeenCalledOnce());
  });
  it("mantém as preferências nativas fora da versão no navegador", () => {
    desktop.isDesktop = false;
    show();
    expect(screen.queryByRole("switch")).toBeNull();
    expect(desktop.startupEnabled).not.toHaveBeenCalled();
  });
  it("permite desligar o widget e abrir sua visualização", async () => {
    show();
    const toggle = screen.getByRole("switch", { name: "Widget de agendamentos em segundo plano" });
    await waitFor(() => expect(toggle).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Ver widget" }));
    await waitFor(() => expect(desktop.showStatusWidget).toHaveBeenCalledOnce());
    fireEvent.click(toggle);
    await waitFor(() => expect(desktop.setWidgetEnabled).toHaveBeenCalledWith(false));
  });
});
