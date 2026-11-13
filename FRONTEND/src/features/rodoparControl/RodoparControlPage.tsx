import { AlertCircle, Crosshair, Hand } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  getOverlayState,
  sendOverlayCommand,
  type OverlayCommand,
  type OverlayPoint,
  type OverlayState,
  type RunSnapshot,
} from "../../lib/api";
import { EventLog } from "../events/EventLog";
import { useAutomationEvents } from "../events/useAutomationEvents";
import { ImportCaptureFile } from "./ImportCaptureFile";
import { RodoparControlLiveView } from "./RodoparControlLiveView";
import "./rodoparControl.css";

interface Props {
  run: RunSnapshot | null;
  hideLiveView?: boolean;
}

const STATE_POLL_MS = 500;

type PendingCapture =
  | { kind: "create"; label: string; ocrText: string; delayMs: number | null }
  | { kind: "capture"; step: number }
  | { kind: "capture_scroll"; step: number }
  | { kind: "capture_scroll_up"; step: number }
  | null;

export function RodoparControlPage({ run, hideLiveView }: Props) {
  const [overlay, setOverlay] = useState<OverlayState | null>(null);
  const [error, setError] = useState("");
  const [pendingCapture, setPendingCapture] = useState<PendingCapture>(null);
  const [newLabel, setNewLabel] = useState("");
  const [newShortcut, setNewShortcut] = useState("");
  const [newOcrText, setNewOcrText] = useState("");
  const [newDelay, setNewDelay] = useState("");
  const [editOpen, setEditOpen] = useState(false);
  const [editingStep, setEditingStep] = useState<number | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editShortcut, setEditShortcut] = useState("");
  const [editOcrText, setEditOcrText] = useState("");
  const [editDelay, setEditDelay] = useState("");
  const [editManualPause, setEditManualPause] = useState(false);
  const [editReliableClick, setEditReliableClick] = useState(false);
  const [draggedStep, setDraggedStep] = useState<number | null>(null);
  const [dragOverStep, setDragOverStep] = useState<number | null>(null);
  const [lastDragResult, setLastDragResult] = useState("");
  const [dismissedManualStep, setDismissedManualStep] = useState<number | null>(null);
  const automationEvents = useAutomationEvents();
  const listRef = useRef<HTMLDivElement | null>(null);
  const runId = run?.id ?? "";
  const runActive = run?.status === "running" || run?.status === "stopping";

  useEffect(() => {
    if (!runId || !runActive) {
      setOverlay(null);
      return;
    }
    let cancelled = false;
    let timer = 0;
    async function poll() {
      try {
        const state = await getOverlayState(runId);
        if (!cancelled) setOverlay(state);
      } catch {
        // keep the last known state; the run may have just finished
      }
      if (!cancelled) timer = window.setTimeout(poll, STATE_POLL_MS);
    }
    void poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [runActive, runId]);

  useEffect(() => {
    setPendingCapture(null);
  }, [runId]);

  useEffect(() => {
    listRef.current?.querySelector(".current")?.scrollIntoView({ block: "nearest" });
  }, [overlay?.currentStep]);

  async function sendCommand(command: OverlayCommand) {
    if (!runId) return;
    setError("");
    try {
      await sendOverlayCommand(runId, command);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao enviar comando.");
    }
  }

  function handleNew() {
    const count = (overlay?.points.length ?? 0) + 1;
    const label = (newLabel || `PASSO-${count}`).trim();
    const shortcut = newShortcut.trim();
    const ocrText = newOcrText.trim();
    const delayMs = newDelay.trim() ? Number(newDelay) : null;
    setNewLabel("");
    setNewShortcut("");
    setNewOcrText("");
    setNewDelay("");
    if (shortcut) {
      void sendCommand({ type: "create", label, shortcut, delayMs });
      return;
    }
    setPendingCapture({ kind: "create", label, ocrText, delayMs });
    void sendCommand({ type: "pause" });
  }

  function handleAdjust() {
    if (editingStep === null) return;
    setPendingCapture({ kind: "capture", step: editingStep });
    void sendCommand({ type: "pause" });
  }

  function handleOpenEdit(point: OverlayPoint) {
    setEditingStep(point.step);
    setEditLabel(point.label);
    setEditShortcut(point.shortcut);
    setEditOcrText(point.ocrText);
    setEditDelay(point.delayMs ? String(point.delayMs) : "");
    setEditManualPause(point.requiresManual);
    setEditReliableClick(point.reliableClick === true);
    setEditOpen(true);
    void sendCommand({ type: "pause" });
  }

  function handleSaveEdit() {
    if (editingStep === null) return;
    void sendCommand({
      type: "edit",
      step: editingStep,
      label: editLabel.trim(),
      shortcut: editShortcut.trim(),
      ocrText: editOcrText.trim(),
      delayMs: editDelay.trim() ? Number(editDelay) : null,
      manualPause: editManualPause,
      reliableClick: editReliableClick,
    });
    setEditOpen(false);
    setEditingStep(null);
  }

  function handleRemoveEditingStep() {
    if (editingStep === null) return;
    if (!window.confirm(`Remover o passo #${editingStep} (${editLabel || "sem nome"})? Isso não tem como desfazer.`)) {
      return;
    }
    void sendCommand({ type: "remove", step: editingStep });
    setEditOpen(false);
    setEditingStep(null);
  }

  function resolveStepAt(x: number, y: number): number | null {
    const hovered = document.elementFromPoint(x, y);
    const row = hovered?.closest<HTMLElement>("[data-step]");
    return row?.dataset.step ? Number(row.dataset.step) : null;
  }

  function handleHandleMouseDown(event: React.MouseEvent<HTMLSpanElement>, step: number) {
    event.preventDefault();
    event.stopPropagation();
    setDraggedStep(step);
    setDragOverStep(step);
    void sendCommand({ type: "pause" });

    function onMove(moveEvent: MouseEvent) {
      setDragOverStep(resolveStepAt(moveEvent.clientX, moveEvent.clientY));
    }

    function onUp(upEvent: MouseEvent) {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      const targetStep = resolveStepAt(upEvent.clientX, upEvent.clientY);
      if (targetStep !== null && targetStep !== step) {
        void sendCommand({ type: "reorder", step, toStep: targetStep });
        setLastDragResult(`Passo #${step} → #${targetStep} enviado.`);
      } else if (targetStep === step) {
        setLastDragResult(`Soltou em cima do próprio passo #${step} — nada a fazer.`);
      } else {
        setLastDragResult(`Não detectei nenhuma linha embaixo do mouse ao soltar (passo #${step}).`);
      }
      setDraggedStep(null);
      setDragOverStep(null);
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  function handleAdjustScroll() {
    if (editingStep === null) return;
    setPendingCapture({ kind: "capture_scroll", step: editingStep });
    void sendCommand({ type: "pause" });
  }

  function handleAdjustScrollUp() {
    if (editingStep === null) return;
    setPendingCapture({ kind: "capture_scroll_up", step: editingStep });
    void sendCommand({ type: "pause" });
  }

  function handleCancelCapture() {
    setPendingCapture(null);
    void sendCommand({ type: "cancel" });
  }

  function handleClear() {
    if (!window.confirm("Remover todos os passos deste mapa?")) return;
    void sendCommand({ type: "clear" });
  }

  function handleCapture(x: number, y: number) {
    if (!pendingCapture) return;
    if (pendingCapture.kind === "create") {
      void sendCommand({
        type: "create",
        label: pendingCapture.label,
        ocrText: pendingCapture.ocrText,
        delayMs: pendingCapture.delayMs,
        x,
        y,
      });
    } else if (pendingCapture.kind === "capture_scroll") {
      void sendCommand({ type: "capture_scroll", step: pendingCapture.step, x, y });
    } else if (pendingCapture.kind === "capture_scroll_up") {
      void sendCommand({ type: "capture_scroll_up", step: pendingCapture.step, x, y });
    } else {
      void sendCommand({ type: "capture", step: pendingCapture.step, x, y });
    }
    setPendingCapture(null);
  }

  const captureHint = !pendingCapture
    ? ""
    : pendingCapture.kind === "capture"
      ? `Clique no novo ponto do passo #${pendingCapture.step}.`
      : pendingCapture.kind === "capture_scroll"
        ? `Clique na setinha de rolar para baixo da barra de rolagem (passo #${pendingCapture.step}).`
        : pendingCapture.kind === "capture_scroll_up"
          ? `Clique na setinha de rolar para cima da barra de rolagem (passo #${pendingCapture.step}).`
          : pendingCapture.ocrText
          ? `CAPTURA - clique no ponto de referência para "${pendingCapture.label}" (procura OCR: ${pendingCapture.ocrText}).`
          : `CAPTURA - clique na tela para criar ${pendingCapture.label}.`;

  const isManualPause = Boolean(overlay?.paused) && Boolean(overlay?.status?.startsWith("AÇÃO MANUAL"));
  const showManualModal = isManualPause && overlay?.currentStep !== dismissedManualStep;

  useEffect(() => {
    if (!isManualPause) setDismissedManualStep(null);
  }, [isManualPause]);

  if (!runId || !runActive) {
    return (
      <section className="panel rodopar-control-page">
        <div className="panel-title">
          <Crosshair size={18} aria-hidden="true" />
          <h2>Controle Rodopar</h2>
        </div>
        <p className="muted">
          Inicie uma execução com o overlay do Rodopar habilitado para usar este controle.
        </p>
        <ImportCaptureFile />
      </section>
    );
  }

  return (
    <div className={hideLiveView ? "rodopar-control-layout compact" : "rodopar-control-layout"}>
      {showManualModal ? (
        <div className="rodopar-control-modal-backdrop">
          <div className="rodopar-control-modal">
            <Hand className="rodopar-control-modal-icon" size={28} strokeWidth={2} />
            <h3>Ação manual necessária</h3>
            <p>
              Passo #{overlay?.currentStep} — {overlay?.currentLabel || "passo atual"}.
              <br />
              Faça a ação na tela (ex.: selecionar a pasta) e clique em Retomar para a automação continuar.
            </p>
            <div className="rodopar-control-modal-actions">
              <button
                className="ghost"
                onClick={() => setDismissedManualStep(overlay?.currentStep ?? null)}
                type="button"
              >
                Fechar aviso
              </button>
              <button className="primary" onClick={() => void sendCommand({ type: "resume" })} type="button">
                Retomar
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <section className="panel rodopar-control-live-panel">
        <div className="panel-title">
          <Crosshair size={18} aria-hidden="true" />
          <h2>Controle Rodopar</h2>
          {overlay?.currentStep ? <span className="pill">#{overlay.currentStep}</span> : null}
          {overlay?.recording ? <span className="pill recording">● gravando</span> : null}
        </div>
        {error ? (
          <div className="error-banner">
            <AlertCircle size={18} aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}
        <p className={`rodopar-control-status${overlay?.status?.startsWith("AÇÃO MANUAL") ? " manual" : ""}`}>
          {overlay?.paused ? "PAUSADO - " : ""}
          {captureHint || overlay?.status || ""}
        </p>
        {!hideLiveView ? (
          <>
            <p className="muted compact">{overlay?.captureFile || "Sem arquivo de captura."}</p>
            <RodoparControlLiveView
              capturing={Boolean(pendingCapture)}
              currentStep={editOpen && editingStep !== null ? editingStep : (overlay?.currentStep ?? null)}
              onCapture={handleCapture}
              points={overlay?.points ?? []}
            />
          </>
        ) : null}
      </section>

      <section className="panel rodopar-control-side-panel">
        <div className="rodopar-control-new">
          <input
            className="rodopar-control-input"
            onChange={(event) => setNewLabel(event.target.value)}
            placeholder="Nome do novo passo"
            value={newLabel}
          />
          <div className="rodopar-control-new-row">
            <input
              onChange={(event) => setNewShortcut(event.target.value)}
              placeholder="Atalho ex: Ctrl+Q"
              value={newShortcut}
            />
            <input
              onChange={(event) => setNewOcrText(event.target.value)}
              placeholder="Texto OCR ex: WebFile"
              value={newOcrText}
            />
            <input
              min={0}
              onChange={(event) => setNewDelay(event.target.value)}
              placeholder="Atraso ms"
              step={100}
              type="number"
              value={newDelay}
            />
          </div>
        </div>

        <div className="rodopar-control-buttons">
          <button onClick={() => void sendCommand({ type: "pause" })} type="button">
            Pausar
          </button>
          <button className="primary" onClick={() => void sendCommand({ type: "resume" })} type="button">
            Retomar
          </button>
          <button className="warn" onClick={() => void sendCommand({ type: "back" })} type="button">
            Voltar 1
          </button>
          <button onClick={() => void sendCommand({ type: "skip" })} type="button">
            Pular
          </button>
          <button className="primary" onClick={handleNew} type="button">
            Novo
          </button>
          <button className="primary" onClick={() => void sendCommand({ type: "save" })} type="button">
            Salvar
          </button>
          <button className="warn" onClick={() => void sendCommand({ type: "loop" })} type="button">
            Definir loop
          </button>
          <button
            className={overlay?.recording ? "danger" : "primary"}
            onClick={() => void sendCommand({ type: overlay?.recording ? "stop_recording" : "start_recording" })}
            type="button"
          >
            {overlay?.recording ? "Parar gravação" : "Gravar cliques"}
          </button>
          <button onClick={handleCancelCapture} type="button">
            Cancelar captura
          </button>
          <button onClick={() => void sendCommand({ type: "finish" })} type="button">
            Fechar
          </button>
          <button className="danger" onClick={handleClear} type="button">
            Limpar todos
          </button>
        </div>

        {editOpen && editingStep !== null ? (
          <div className="rodopar-control-new">
            <p className="muted compact">
              Editando passo #{editingStep} — troque nome/atalho/OCR sem apagar e recriar.
            </p>
            <input
              className="rodopar-control-input"
              onChange={(event) => setEditLabel(event.target.value)}
              placeholder="Nome do passo"
              value={editLabel}
            />
            <div className="rodopar-control-new-row">
              <input
                onChange={(event) => setEditShortcut(event.target.value)}
                placeholder="Atalho ex: Ctrl+Q"
                value={editShortcut}
              />
              <input
                onChange={(event) => setEditOcrText(event.target.value)}
                placeholder="Texto OCR ex: WebFile em"
                value={editOcrText}
              />
              <input
                min={0}
                onChange={(event) => setEditDelay(event.target.value)}
                placeholder="Atraso ms"
                step={100}
                type="number"
                value={editDelay}
              />
            </div>
            <div className="rodopar-control-toggles">
              <label className="rodopar-control-checkbox">
                <input
                  checked={editManualPause}
                  onChange={(event) => setEditManualPause(event.target.checked)}
                  type="checkbox"
                />
                Pausar e pedir ação manual (aguarda clique em Retomar toda vez que passar por aqui)
              </label>
              <label className="rodopar-control-checkbox">
                <input
                  checked={editReliableClick}
                  onChange={(event) => setEditReliableClick(event.target.checked)}
                  type="checkbox"
                />
                Forçar clique duplo neste passo (mais confiável para fechar janelas)
              </label>
            </div>
            <div className="rodopar-control-buttons">
              <button className="primary" onClick={handleSaveEdit} type="button">
                Salvar campos
              </button>
              <button onClick={handleAdjust} type="button">
                Ajustar posição
              </button>
              <button onClick={handleAdjustScroll} type="button">
                Ajustar rolagem (descer)
              </button>
              <button onClick={handleAdjustScrollUp} type="button">
                Ajustar rolagem (subir)
              </button>
              <button
                onClick={() => {
                  setEditOpen(false);
                  setEditingStep(null);
                }}
                type="button"
              >
                Cancelar edição
              </button>
              <button className="danger" onClick={handleRemoveEditingStep} type="button">
                Remover este passo
              </button>
            </div>
          </div>
        ) : null}

        {draggedStep !== null ? (
          <p className="muted compact">
            Arrastando passo #{draggedStep} → {dragOverStep !== null ? `sobre passo #${dragOverStep}` : "(nenhuma linha detectada embaixo do mouse)"}
          </p>
        ) : lastDragResult ? (
          <p className="muted compact">{lastDragResult}</p>
        ) : null}

        <div className="rodopar-control-list" ref={listRef}>
          {(overlay?.points ?? []).map((point) => {
            const rightCol = point.shortcut
              ? `⌨ ${point.shortcut}`
              : point.ocrText
                ? `🔍 ${point.ocrText} ${point.hasScrollUpTarget ? "⇧" : ""}${point.hasScrollTarget ? "⇩" : point.hasScrollUpTarget ? "" : "⚠"}`
                : `${point.x},${point.y}`;
            const delayTag = point.delayMs ? ` · ${point.delayMs}ms` : "";
            const tplIcon = point.shortcut ? "⌨" : point.ocrText ? "🔍" : point.hasTemplate ? "●" : "–";
            const tplTitle = point.shortcut
              ? "Atalho de teclado"
              : point.ocrText
                ? "Busca por texto (OCR)"
                : point.hasTemplate
                  ? "Template capturado"
                  : "Sem template (clique fixo)";
            const isCurrent = point.step === overlay?.currentStep;
            const isEditing = editOpen && point.step === editingStep;
            const isDragging = draggedStep === point.step;
            const isDropTarget = draggedStep !== null && dragOverStep === point.step && !isDragging;
            return (
              <div
                className={`rodopar-control-row${point.loopPoint ? " loop" : ""}${isCurrent ? " current" : ""}${isEditing ? " editing" : ""}${isDragging ? " dragging" : ""}${isDropTarget ? " drop-target" : ""}`}
                data-step={point.step}
                key={point.step}
                onClick={() => void sendCommand({ type: "select", step: point.step })}
              >
                <span
                  className="rodopar-control-row-handle"
                  onClick={(event) => event.stopPropagation()}
                  onMouseDown={(event) => handleHandleMouseDown(event, point.step)}
                  title="Arraste para reordenar"
                >
                  ⠿
                </span>
                <span className="rodopar-control-row-step">{point.step}</span>
                <span className="rodopar-control-row-label" title={`${point.label}${delayTag}`}>
                  {point.loopPoint ? "LOOP - " : ""}
                  {point.requiresManual ? "✋ " : ""}
                  {point.label}
                  {delayTag}
                </span>
                <span className="rodopar-control-row-xy">{rightCol}</span>
                <span
                  className="rodopar-control-row-tpl"
                  style={{ color: point.hasTemplate ? "#16a34a" : "#9ca3af" }}
                  title={tplTitle}
                >
                  {tplIcon}
                </span>
                <span className="rodopar-control-row-actions">
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      handleOpenEdit(point);
                    }}
                    title="Editar este passo"
                    type="button"
                  >
                    ✎
                  </button>
                </span>
              </div>
            );
          })}
        </div>

        <EventLog connected={automationEvents.connected} events={automationEvents.events} />
        <ImportCaptureFile />
      </section>
    </div>
  );
}
