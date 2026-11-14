import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { UpdateStatus } from "@/services";
import { UpdateDialog } from "./update-dialog";

afterEach(cleanup);

function setup(changes: Partial<UpdateStatus> = {}, running = false) {
  const data: UpdateStatus = {
    status: "available",
    current_version: "0.1.34-r8",
    received_bytes: 0,
    checked_at: null,
    message: "Uma nova versão está disponível.",
    can_install: true,
    release: {
      schema_version: 1,
      version: "0.1.34-r9",
      title: "Atualização do Cargo Hub",
      notes: "Corrige a consulta e a interface.",
      published_at: "2026-11-13T17:00:00Z",
      file: "NovelisCargoHubSetup-0.1.34-r9.exe",
      sha256: "a".repeat(64),
      size: 1048576,
      architecture: "x64",
    },
    ...changes,
  };
  const actions = {
    onOpenChange: vi.fn(),
    onCheck: vi.fn(),
    onDownload: vi.fn(),
    onInstall: vi.fn(),
  };
  render(
    <UpdateDialog
      open
      data={data}
      checking={false}
      busy={false}
      automationRunning={running}
      {...actions}
    />,
  );
  return actions;
}

describe("modal de atualização", () => {
  it("mostra as versões e baixa somente após a ação do operador", () => {
    const actions = setup();
    expect(screen.getByText("Versão atual 0.1.34-r8")).toBeInTheDocument();
    expect(screen.getByText("0.1.34-r9")).toBeInTheDocument();
    expect(actions.onDownload).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Baixar atualização" }));
    expect(actions.onDownload).toHaveBeenCalledOnce();
  });

  it("mostra progresso e permite fechar durante o download", () => {
    const actions = setup({ status: "downloading", received_bytes: 524288 });
    expect(screen.getByText(/50%/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Instalar atualização" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Agora não" }));
    expect(actions.onOpenChange).toHaveBeenCalledWith(false);
  });

  it("aguarda a automação encerrar para permitir instalar", () => {
    setup({ status: "ready" }, true);
    expect(screen.getByRole("button", { name: "Instalar atualização" })).toBeDisabled();
  });

  it("restringe a instalação à cópia instalada", () => {
    setup({ status: "ready", can_install: false });
    expect(screen.getByRole("button", { name: "Instalar atualização" })).toBeDisabled();
  });

  it("mostra a falha de acesso ao feed e permite consultar novamente", () => {
    const actions = setup({
      status: "error",
      release: null,
      message: "O servidor exige autorização para leitura das atualizações.",
    });
    expect(screen.getByRole("alert")).toHaveTextContent("exige autorização");
    fireEvent.click(screen.getByRole("button", { name: "Verificar novamente" }));
    expect(actions.onCheck).toHaveBeenCalledOnce();
  });
});
