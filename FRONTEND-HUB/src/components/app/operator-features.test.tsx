import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { HubNotification } from "@/services";
import { AppDialogs, useAppDialogs } from "./app-dialogs";
import { NotificationDialog } from "./notification-dialog";
import { ScheduleForm } from "./schedule-form";
import { emptySchedule } from "@/services/schedule-options";
import { selectOption } from "@/test/select-option";

beforeEach(() => {
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
  vi.unstubAllGlobals();
});

const notice: HubNotification = {
  id: "notice-1",
  title: "Aviso do desenvolvedor",
  body: "Mensagem <script>literal</script>",
  severity: "warning",
  author: "Equipe de teste",
  created_at: "2026-11-13T10:00:00Z",
  archived_at: null,
  expires_at: null,
  read_at: null,
};

describe("notificações e agendamentos", () => {
  it("mostra o comunicado como texto e registra leitura pela ação do operador", () => {
    const onRead = vi.fn();
    render(
      <NotificationDialog
        open
        items={[notice]}
        selectedId={notice.id}
        onSelect={vi.fn()}
        onOpenChange={vi.fn()}
        onRead={onRead}
        saving={false}
        error={false}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByText(notice.body)).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(onRead).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Marcar como lida" }));
    expect(onRead).toHaveBeenCalledExactlyOnceWith(notice.id);
  });

  it("identifica um aviso já lido", () => {
    render(
      <NotificationDialog
        open
        items={[{ ...notice, read_at: "2026-11-13T11:00:00Z" }]}
        selectedId={notice.id}
        onSelect={vi.fn()}
        onOpenChange={vi.fn()}
        onRead={vi.fn()}
        saving={false}
        error={false}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Mensagem lida" })).toBeDisabled();
  });

  it("mantém um modal ativo por vez", () => {
    function Controls() {
      const dialogs = useAppDialogs();
      return (
        <>
          <output data-testid="active-dialog">{dialogs.active ?? "none"}</output>
          <button onClick={() => dialogs.show("notifications")}>Abrir avisos</button>
          <button onClick={() => dialogs.show("updates")}>Abrir versões</button>
          <button onClick={() => dialogs.hide("notifications")}>Fechar avisos</button>
        </>
      );
    }
    render(
      <AppDialogs>
        <Controls />
      </AppDialogs>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Abrir avisos" }));
    fireEvent.click(screen.getByRole("button", { name: "Abrir versões" }));
    expect(screen.getByTestId("active-dialog")).toHaveTextContent("notifications");
    fireEvent.click(screen.getByRole("button", { name: "Fechar avisos" }));
    fireEvent.click(screen.getByRole("button", { name: "Abrir versões" }));
    expect(screen.getByTestId("active-dialog")).toHaveTextContent("updates");
  });

  it("configura 08:00, dias anteriores e execução somente PDF", async () => {
    const save = vi.fn();
    function Form() {
      const [value, setValue] = useState(emptySchedule);
      return (
        <ScheduleForm
          value={value}
          onChange={setValue}
          onSave={() => save(value)}
          onCancel={vi.fn()}
          saving={false}
          editing={false}
        />
      );
    }
    render(<Form />);
    expect(screen.getByLabelText("Horário de início")).toHaveTextContent("08:00");
    fireEvent.change(screen.getByLabelText("Nome do agendamento"), {
      target: { value: "PDFs da manhã" },
    });
    await selectOption("Etapa", "Baixar PDFs");
    fireEvent.change(screen.getByLabelText("Dias anteriores incluídos"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Escolher" }));
    fireEvent.click(screen.getByRole("button", { name: /^Dom$/ }));
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    expect(save).toHaveBeenCalledWith({
      name: "PDFs da manhã",
      time: "08:00",
      days_back: 2,
      flow: "somente_pdf",
      weekdays: [0, 1, 2, 3, 4, 5],
      enabled: true,
      runs_per_day: 1,
      interval_minutes: 60,
      max_retries: 0,
      retry_interval_minutes: 5,
    });
  });

  it("exige ao menos um dia para salvar o agendamento", () => {
    render(
      <ScheduleForm
        value={{ ...emptySchedule(), name: "Rotina válida", weekdays: [] }}
        onChange={vi.fn()}
        onSave={vi.fn()}
        onCancel={vi.fn()}
        saving={false}
        editing={false}
      />,
    );
    expect(screen.getByRole("button", { name: "Salvar" })).toBeDisabled();
    expect(screen.getByText("Selecione ao menos um dia.")).toBeInTheDocument();
  });
});
