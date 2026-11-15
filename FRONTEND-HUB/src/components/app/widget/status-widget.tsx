import { useEffect, useState } from "react";
import { desktop } from "@/services/desktop";
import {
  readWidgetSnapshot,
  widgetSnapshotKey,
  widgetStatus,
  type WidgetSnapshot,
} from "@/services/status-widget";
import { scheduleDate, scheduleRemaining } from "@/services/schedule-options";
import { BrandMark } from "../brand";
import { FluentIcon } from "../fluent-icon";
import { AppearanceProvider } from "../appearance-provider";
import { WidgetActivity } from "./widget-activity";
import { chatAlertKey, readChatAlert, type ChatAlert } from "@/services/chat-alert";
import "./status-widget.css";

export function StatusWidget() {
  const [snapshot, setSnapshot] = useState(readWidgetSnapshot);
  const [chat, setChat] = useState(readChatAlert);
  const [now, setNow] = useState(Date.now);
  const [error, setError] = useState("");
  const [compact, setCompact] = useState(true);
  const [resizing, setResizing] = useState(false);
  useEffect(() => {
    void desktop
      .setWidgetCompact(true)
      .catch(() => setError("Não foi possível ajustar o tamanho do widget."));
  }, []);
  useEffect(() => {
    const update = () => {
      setSnapshot(readWidgetSnapshot());
      setChat(readChatAlert());
      setNow(Date.now());
    };
    const storage = (event: StorageEvent) => {
      if (event.key === widgetSnapshotKey || event.key === chatAlertKey || event.key === null)
        update();
    };
    const timer = window.setInterval(update, 1_000);
    window.addEventListener("storage", storage);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("storage", storage);
    };
  }, []);
  const act = (operation: Promise<void>) =>
    void operation.catch(() =>
      setError("Não foi possível abrir a janela. Use o ícone na bandeja."),
    );
  const toggleCompact = async () => {
    setResizing(true);
    setError("");
    try {
      await desktop.setWidgetCompact(!compact);
      setCompact(!compact);
    } catch {
      setError("Não foi possível alterar o tamanho do widget.");
    } finally {
      setResizing(false);
    }
  };
  return (
    <AppearanceProvider>
      <WidgetContent
        snapshot={snapshot}
        chat={chat}
        now={now}
        error={error}
        compact={compact}
        resizing={resizing}
        onToggle={() => void toggleCompact()}
        onOpen={(page) => act(desktop.openMainFromWidget(page))}
        onClose={() => act(desktop.dismissStatusWidget())}
      />
    </AppearanceProvider>
  );
}

export function WidgetContent({
  snapshot,
  chat = null,
  now,
  error = "",
  compact = false,
  resizing = false,
  onToggle,
  onOpen,
  onClose,
}: {
  snapshot: WidgetSnapshot | null;
  chat?: ChatAlert | null;
  now: number;
  error?: string;
  compact?: boolean;
  resizing?: boolean;
  onToggle(): void;
  onOpen(page: "/monitor" | "/agendamentos" | "/conversas"): void;
  onClose(): void;
}) {
  const status = widgetStatus(snapshot, now);
  const active =
    status.connected && (snapshot?.state === "executando" || snapshot?.state === "parando");
  const progress = snapshot?.total
    ? Math.min(100, Math.max(0, Math.round((snapshot.done / snapshot.total) * 100)))
    : 0;
  return (
    <section
      className="status-widget-shell"
      data-compact={compact}
      aria-label="Widget de agendamentos"
    >
      <header className="status-widget-header">
        <div
          className="status-widget-drag"
          onPointerDown={(event) => {
            if (event.button === 0) void desktop.dragStatusWidget().catch(() => {});
          }}
          title="Arrastar widget"
        >
          <BrandMark className="h-6 w-6" />
          <span>Cargo Hub</span>
        </div>
        <button
          type="button"
          className="status-widget-icon"
          onClick={onToggle}
          disabled={resizing}
          aria-label={compact ? "Expandir widget" : "Recolher widget"}
          title={compact ? "Expandir widget" : "Recolher widget"}
          aria-expanded={!compact}
        >
          <FluentIcon name={compact ? "restore" : "minimize"} />
        </button>
        <button
          type="button"
          className="status-widget-icon"
          onClick={onClose}
          aria-label="Ocultar widget"
          title="Ocultar widget"
        >
          <FluentIcon name="cancel" />
        </button>
      </header>
      <div className="status-widget-body">
        <WidgetActivity snapshot={snapshot} now={now} />
        {chat && status.connected && (
          <button
            type="button"
            className="status-widget-message"
            onClick={() => onOpen("/conversas")}
            title={chat.room}
          >
            <FluentIcon name="message" />
            <span>
              {chat.unread} {chat.unread === 1 ? "nova mensagem" : "novas mensagens"}
            </span>
          </button>
        )}
        {compact && chat && status.connected ? null : compact ? (
          <div
            className="status-widget-mini-next"
            title={status.connected ? snapshot?.next?.name : undefined}
          >
            <FluentIcon name="calendar" />
            <span>
              {status.connected
                ? snapshot?.next
                  ? `${snapshot.next.attempt > 0 ? "Nova tentativa" : "Próxima rotina"} · ${scheduleDate(snapshot.next.at, new Date(now))}`
                  : "Nenhuma rotina programada"
                : "Aguardando atualização"}
            </span>
          </div>
        ) : (
          <>
            <div className="status-widget-execution">
              {active && snapshot ? (
                <>
                  <div className="status-widget-progress-label">
                    <span>{snapshot.cte ? `CT-e ${snapshot.cte}` : "Em andamento"}</span>
                    <span>
                      {snapshot.done} / {snapshot.total}
                    </span>
                  </div>
                  <div
                    className="status-widget-progress"
                    role="progressbar"
                    aria-label="Progresso da execução"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={progress}
                  >
                    <span style={{ width: `${progress}%` }} />
                  </div>
                  <p title={snapshot.detail}>{snapshot.detail || "Acompanhando execução"}</p>
                </>
              ) : (
                <p>
                  {status.connected
                    ? snapshot?.failure
                      ? `${snapshot.failure.name} · ${snapshot.failure.message || "Falha registrada"}`
                      : `${snapshot?.activeSchedules ?? 0} agendamento(s) ativo(s)`
                    : "Abra o Cargo Hub para conferir a conexão e a sessão."}
                </p>
              )}
            </div>
            <div className="status-widget-next">
              <div>
                <FluentIcon name="calendar" />
                <span>
                  {snapshot?.next && snapshot.next.attempt > 0
                    ? "Próxima tentativa"
                    : "Próximo agendamento"}
                </span>
              </div>
              {status.connected && snapshot?.next ? (
                <>
                  <strong>{scheduleDate(snapshot.next.at, new Date(now))}</strong>
                  <p title={snapshot.next.name}>{snapshot.next.name}</p>
                  <small>{scheduleRemaining(snapshot.next.at, now)}</small>
                </>
              ) : (
                <p>{status.connected ? "Nenhuma rotina programada" : "Aguardando atualização"}</p>
              )}
            </div>
          </>
        )}
        {error && (
          <p className="status-widget-error" role="alert">
            {error}
          </p>
        )}
      </div>
      {!compact && (
        <footer className="status-widget-footer">
          <div className="status-widget-actions">
            <button type="button" onClick={() => onOpen("/monitor")}>
              <FluentIcon name="monitor" />
              Monitor
            </button>
            <button type="button" onClick={() => onOpen("/agendamentos")}>
              <FluentIcon name="calendar" />
              Agendamentos
            </button>
          </div>
          <div className="status-widget-updated">
            {status.connected ? "Conectado" : "Sem dados atuais"}
            <span>
              {snapshot
                ? new Date(snapshot.updatedAt).toLocaleTimeString("pt-BR", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "—"}
            </span>
          </div>
        </footer>
      )}
    </section>
  );
}
