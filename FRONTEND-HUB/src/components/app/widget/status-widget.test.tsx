import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { makeWidgetSnapshot } from "@/services/status-widget";
import { desktop } from "@/services/desktop";
import { StatusWidget, WidgetContent } from "./status-widget";

vi.mock("@/services/desktop", () => ({
  desktop: {
    dragStatusWidget: vi.fn().mockResolvedValue(undefined),
    setWidgetCompact: vi.fn().mockResolvedValue(undefined),
    setTheme: vi.fn().mockResolvedValue(undefined),
  },
}));
beforeEach(() => vi.mocked(desktop.setWidgetCompact).mockResolvedValue(undefined));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});
const now = Date.parse("2026-11-15T12:00:00-03:00");
const snapshot = makeWidgetSnapshot({
  run: {
    id: "r1",
    state: "executando",
    flow: "somente_pdf",
    etapaAtual: "pdf",
    cteAtual: "1-10-123",
    processados: 2,
    total: 4,
    iniciadoEm: null,
    stages: [],
  },
  schedules: undefined,
  connection: "connected",
  now,
});

it("mostra a geração em andamento e permite abrir monitor e agendamentos", () => {
  const open = vi.fn();
  const close = vi.fn();
  render(
    <WidgetContent
      snapshot={snapshot}
      now={now}
      onOpen={open}
      onClose={close}
      onToggle={vi.fn()}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Gerando PDF");
  expect(screen.getByText("CT-e 1-10-123")).toBeVisible();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
  fireEvent.click(screen.getByRole("button", { name: "Monitor" }));
  expect(open).toHaveBeenLastCalledWith("/monitor");
  fireEvent.click(screen.getByRole("button", { name: "Agendamentos" }));
  expect(open).toHaveBeenLastCalledWith("/agendamentos");
  fireEvent.click(screen.getByRole("button", { name: "Ocultar widget" }));
  expect(close).toHaveBeenCalledOnce();
});

it("retira o progresso ao perder atualização e identifica uma nova tentativa", () => {
  const next = { name: "Rotina da manhã", at: "2026-11-15T12:10:00-03:00", attempt: 1 };
  const view = render(
    <WidgetContent
      snapshot={{ ...snapshot, next }}
      now={now}
      onOpen={vi.fn()}
      onClose={vi.fn()}
      onToggle={vi.fn()}
    />,
  );
  expect(screen.getByText("Próxima tentativa")).toBeVisible();
  expect(screen.getByText("Rotina da manhã")).toBeVisible();
  view.rerender(
    <WidgetContent
      snapshot={{ ...snapshot, next }}
      now={now + 30_000}
      onOpen={vi.fn()}
      onClose={vi.fn()}
      onToggle={vi.fn()}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Aguardando atualização");
  expect(screen.queryByRole("progressbar")).toBeNull();
  expect(screen.queryByText("Rotina da manhã")).toBeNull();
});

it("mantém status e próximo horário na visualização reduzida", () => {
  const toggle = vi.fn();
  render(
    <WidgetContent
      snapshot={{
        ...snapshot,
        next: { name: "Rotina diária", at: "2026-11-15T13:00:00-03:00", attempt: 0 },
      }}
      now={now}
      compact
      onOpen={vi.fn()}
      onClose={vi.fn()}
      onToggle={toggle}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Gerando PDF");
  expect(screen.getByText(/Próxima rotina · Hoje, 13:00/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Monitor" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Expandir widget" }));
  expect(toggle).toHaveBeenCalledOnce();
});

it("avisa sobre mensagens no widget compacto e abre a conversa", () => {
  const open = vi.fn();
  render(
    <WidgetContent
      snapshot={snapshot}
      now={now}
      compact
      chat={{ unread: 2, room: "Financeiro", receivedAt: now }}
      onOpen={open}
      onClose={vi.fn()}
      onToggle={vi.fn()}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Gerando PDF");
  fireEvent.click(screen.getByRole("button", { name: "2 novas mensagens" }));
  expect(open).toHaveBeenCalledWith("/conversas");
  expect(screen.queryByText("Nenhuma rotina programada")).toBeNull();
});

it("inicia compacto, permite expandir e volta compacto na próxima abertura", async () => {
  localStorage.setItem("cargo-hub.status-widget.compact", "false");
  const view = render(<StatusWidget />);
  await waitFor(() => expect(desktop.setWidgetCompact).toHaveBeenCalledWith(true));
  fireEvent.click(screen.getByRole("button", { name: "Expandir widget" }));
  expect(await screen.findByRole("button", { name: "Recolher widget" })).toBeVisible();
  expect(desktop.setWidgetCompact).toHaveBeenLastCalledWith(false);
  view.unmount();
  render(<StatusWidget />);
  expect(screen.getByRole("button", { name: "Expandir widget" })).toBeVisible();
  await waitFor(() => expect(desktop.setWidgetCompact).toHaveBeenLastCalledWith(true));
});

it("mantém a visualização quando o redimensionamento nativo falha", async () => {
  render(<StatusWidget />);
  await waitFor(() => expect(desktop.setWidgetCompact).toHaveBeenCalledWith(true));
  vi.mocked(desktop.setWidgetCompact).mockRejectedValueOnce(new Error("resize_failed"));
  fireEvent.click(screen.getByRole("button", { name: "Expandir widget" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível alterar o tamanho");
  expect(screen.getByRole("button", { name: "Expandir widget" })).toBeEnabled();
  expect(localStorage.getItem("cargo-hub.status-widget.compact")).toBeNull();
});
