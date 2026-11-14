import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { desktop } from "@/services/desktop";
import { ReleasePublisher } from "./release-publisher";

const fixture = vi.hoisted(() => ({
  getPublishStatus: vi.fn(),
  publishRelease: vi.fn(),
  checkUpdates: vi.fn(),
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: fixture, mode: "local", baseUrl: "http://test/api/hub" }),
}));
vi.mock("@/services/desktop", () => ({ desktop: { pickInstaller: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  fixture.getPublishStatus.mockResolvedValue({
    status: "idle",
    sent_bytes: 0,
    total_bytes: 0,
    message: "",
  });
  fixture.publishRelease.mockResolvedValue({
    status: "uploading",
    sent_bytes: 0,
    total_bytes: 1024,
    message: "Enviando…",
  });
  vi.mocked(desktop.pickInstaller).mockResolvedValue(
    "C:\\Releases\\NovelisCargoHubSetup-0.1.35.exe",
  );
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ReleasePublisher />
    </QueryClientProvider>,
  );
}

describe("publicação pelo aplicativo", () => {
  it("seleciona o instalador e exige a autorização de distribuição antes de enviar", async () => {
    show();
    const button = screen.getByRole("button", { name: "Publicar atualização" });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Selecionar" }));
    await waitFor(() => expect(screen.getByLabelText("Versão")).toHaveValue("0.1.35"));
    fireEvent.change(screen.getByLabelText("Notas da atualização"), {
      target: { value: "Correções desta versão" },
    });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(button);
    await waitFor(() =>
      expect(fixture.publishRelease).toHaveBeenCalledWith({
        installer_path: "C:\\Releases\\NovelisCargoHubSetup-0.1.35.exe",
        version: "0.1.35",
        notes: "Correções desta versão",
        distribution_authorized: true,
      }),
    );
  });

  it("mostra o progresso de envio", async () => {
    fixture.getPublishStatus.mockResolvedValue({
      status: "uploading",
      sent_bytes: 512,
      total_bytes: 1024,
      message: "Enviando…",
    });
    show();
    await expect(
      screen.findByRole("progressbar", { name: "Envio do instalador" }),
    ).resolves.toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByRole("button", { name: "Publicando…" })).toBeDisabled();
  });
});
