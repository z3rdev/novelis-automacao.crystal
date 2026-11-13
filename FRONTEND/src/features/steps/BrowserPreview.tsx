import { Globe } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

import {
  API_BASE,
  browserSiteUrl,
  clickBrowser,
  confirmManualLogin,
  getBrowserState,
  type AutomationEvent,
  type RodoparMapPoint,
  type RunSnapshot,
  type StepDefinition,
} from "../../lib/api";
import type { PreviewCapturePoint } from "../mapping/mappingTypes";
import { mapPointKey } from "../mapping/mappingUtils";
import {
  buildRegionBoxes,
  clamp,
  PREVIEW_VIEWPORT,
  regionBoxStyle,
} from "./browserPreviewGeometry";
import { OwnBrowserNotice } from "./OwnBrowserNotice";
import { LocalFlowStatus } from "./LocalFlowStatus";
import { LiveBrowserSnapshot } from "./LiveBrowserSnapshot";
import { BrowserPreviewToolbar } from "./BrowserPreviewToolbar";
import { PreviewMarkers, type PreviewDraggedPoint } from "./PreviewMarkers";
import { RodoparLoginGate } from "./RodoparLoginGate";
import { isRodoparConfirmEvent, isRodoparWaitEvent } from "./rodoparGateEvents";
import { RodoparStatusOnly } from "./RodoparStatusOnly";
import { apiErrorMessage } from "./previewErrors";
import { isStepDefinition, type PreviewCommand, type RunStartPayload, type StepEventPayload } from "./previewEvents";
import { previewTargetForFlow, SEFAZ_CHAVE_SELECTOR } from "./previewTargets";

interface Props {
  captureEnabled?: boolean;
  mappedPoints?: RodoparMapPoint[];
  pointDragEnabled?: boolean;
  selectedMapPoint?: RodoparMapPoint | null;
  portalUrl: string;
  rodoparUrl: string;
  run: RunSnapshot | null;
  step: StepDefinition | null;
  onCapturePoint?: (point: PreviewCapturePoint) => void;
  onMoveMapPoint?: (point: RodoparMapPoint, next: PreviewCapturePoint) => void;
  events?: AutomationEvent[];
}

const PREVIEW_SOURCE = "automacao-novelis-preview";

export function BrowserPreview({
  captureEnabled = false,
  mappedPoints = [],
  pointDragEnabled = false,
  selectedMapPoint = null,
  portalUrl,
  rodoparUrl,
  run,
  step,
  onCapturePoint,
  onMoveMapPoint,
  events = [],
}: Props) {
  const [frameTarget, setFrameTarget] = useState("");
  const [frameKey, setFrameKey] = useState(0);
  const [visible, setVisible] = useState(false);
  const [ownBrowserNoticeOpen, setOwnBrowserNoticeOpen] = useState(false);
  const [manualLoginHint, setManualLoginHint] = useState(false);
  const [manualLoginConfirming, setManualLoginConfirming] = useState(false);
  const [manualLoginError, setManualLoginError] = useState("");
  const [manualLoginSubmitted, setManualLoginSubmitted] = useState(false);
  const [draggedPoint, setDraggedPoint] = useState<PreviewDraggedPoint | null>(null);
  const [captureDraft, setCaptureDraft] = useState<PreviewCapturePoint | null>(null);
  const captureDraftRef = useRef<PreviewCapturePoint | null>(null);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const frameOriginRef = useRef("*");
  const dellmarLoginTimerRef = useRef<number | null>(null);
  const lastEventIdRef = useRef(0);
  const openedRunIdRef = useRef("");
  const pendingSefazKeyRef = useRef("");
  const runPayloadRef = useRef<RunStartPayload>({});
  const automationRunning = run?.status === "running" || run?.status === "stopping";
  const simulationRun = Boolean(run?.dry_run && run.status !== "idle");
  const localStatusFlow = run?.flow === "comprovante-local";
  const rodoparPdfFlow = run?.flow === "pdf-rodopar" || run?.flow === "rodopar-pdf";
  const rodoparWaitEvent = events.find((event) => isRodoparWaitEvent(event, run?.id));
  const rodoparConfirmedSeen = events.some((event) => isRodoparConfirmEvent(event, run?.id));
  const rodoparStatusOnly = rodoparPdfFlow || Boolean(rodoparWaitEvent);
  const ownBrowserFlow = !run?.dry_run && ["xml-sefaz", "chamado-novelis"].includes(run?.flow || "");
  const liveSnapshotMode =
    automationRunning &&
    !localStatusFlow &&
    !rodoparStatusOnly &&
    (run?.flow === "pendentes" || !run?.dry_run);
  const showOwnBrowserNotice = ownBrowserNoticeOpen || (automationRunning && ownBrowserFlow);
  const loginTarget = portalUrl || "https://webcloud16.datapardc.com/";
  const html5Target = rodoparUrl || "https://webcloud16.datapardc.com/software/html5.html";
  const defaultTarget = loginTarget;
  const frameUrl = useMemo(
    () => browserSiteUrl(frameTarget || defaultTarget),
    [defaultTarget, frameTarget],
  );

  const markerStyle = step
    ? {
        left: `${(step.x / step.viewport.width) * 100}%`,
        top: `${(step.y / step.viewport.height) * 100}%`,
      }
    : undefined;
  const displayPoints = mappedPoints.map((point) =>
    draggedPoint?.key === mapPointKey(point)
      ? {
          ...point,
          x: draggedPoint.x,
          y: draggedPoint.y,
          x2: draggedPoint.x2 ?? point.x2,
          y2: draggedPoint.y2 ?? point.y2,
        }
      : point,
  );
  const regionBoxes = buildRegionBoxes(displayPoints);
  const showRodoparLoginModal =
    automationRunning &&
    rodoparStatusOnly &&
    !rodoparConfirmedSeen &&
    !manualLoginSubmitted &&
    (manualLoginHint || Boolean(rodoparWaitEvent));

  useEffect(() => {
    try {
      frameOriginRef.current = new URL(frameUrl).origin;
    } catch {
      frameOriginRef.current = "*";
    }
  }, [frameUrl]);

  useEffect(() => {
    if (!run?.id || !automationRunning || openedRunIdRef.current === run.id) return;
    openedRunIdRef.current = run.id;
    if (rodoparStatusOnly) {
      setVisible(false);
      setFrameTarget("");
      return;
    }
    const target = previewTargetForFlow(run.flow, loginTarget);
    if (!target) {
      setVisible(false);
      setFrameTarget("");
      return;
    }
    setFrameTarget(target);
    setVisible(true);
    setFrameKey((current) => current + 1);
  }, [automationRunning, loginTarget, rodoparStatusOnly, run?.flow, run?.id]);

  useEffect(() => {
    if (automationRunning && ownBrowserFlow) setOwnBrowserNoticeOpen(true);
  }, [automationRunning, ownBrowserFlow, run?.id]);

  useEffect(() => {
    setManualLoginHint(false);
    setManualLoginConfirming(false);
    setManualLoginError("");
    setManualLoginSubmitted(false);
  }, [run?.id, run?.status]);

  useEffect(() => {
    if (!ownBrowserNoticeOpen) return;
    let cancelled = false;
    let timer = 0;
    async function pollBrowserState() {
      try {
        const state = await getBrowserState();
        if (!cancelled && !state.open && !automationRunning) setOwnBrowserNoticeOpen(false);
      } catch {
        if (!cancelled && !automationRunning) setOwnBrowserNoticeOpen(false);
      }
      if (!cancelled) timer = window.setTimeout(pollBrowserState, 1000);
    }
    void pollBrowserState();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [automationRunning, ownBrowserNoticeOpen]);

  function handleFrameLoad() {
    if (dellmarLoginTimerRef.current) window.clearTimeout(dellmarLoginTimerRef.current);
    if (pendingSefazKeyRef.current) scheduleSefazKeyFill(pendingSefazKeyRef.current);
    window.setTimeout(() => {
      try {
        const href = iframeRef.current?.contentWindow?.location.href || "";
        if (href.startsWith(window.location.origin)) setFrameKey((current) => current + 1);
      } catch {
        return;
      }
    }, 100);
  }

  function postPreviewCommand(command: PreviewCommand) {
    const target = iframeRef.current?.contentWindow;
    if (!target) return;
    target.postMessage(
      { source: PREVIEW_SOURCE, ...command },
      frameOriginRef.current,
    );
  }

  function scheduleSefazKeyFill(cteId: string) {
    pendingSefazKeyRef.current = cteId;
    [150, 600, 1400, 2800].forEach((delay) => {
      window.setTimeout(() => {
        postPreviewCommand({
          type: "preview.set_value",
          selector: SEFAZ_CHAVE_SELECTOR,
          text: cteId,
        });
      }, delay);
    });
  }

  function clickPreviewOrBrowser(x: number, y: number) {
    if (liveSnapshotMode) {
      void clickBrowser(x, y).catch(() => null);
      return;
    }
    postPreviewCommand({
      type: "preview.click",
      x,
      y,
      viewportWidth: PREVIEW_VIEWPORT.width,
      viewportHeight: PREVIEW_VIEWPORT.height,
    });
  }

  function clickLegalNotice() {
    if (automationRunning && rodoparPdfFlow) setManualLoginHint(true);
    clickPreviewOrBrowser(300, 430);
  }

  function clickDellmarApp() {
    if (automationRunning && rodoparPdfFlow) setManualLoginHint(true);
    clickPreviewOrBrowser(84, 385);
  }

  async function confirmRodoparLogin() {
    if (!run?.id || manualLoginConfirming) return;
    setManualLoginConfirming(true);
    setManualLoginError("");
    try {
      await confirmManualLogin(run.id);
      setManualLoginSubmitted(true);
      setManualLoginHint(false);
    } catch (error) {
      setManualLoginError(apiErrorMessage(error));
    } finally {
      setManualLoginConfirming(false);
    }
  }

  function handleCapturePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const point = pointFromEvent(event.clientX, event.clientY, rect);
    const draft = { ...point, x2: point.x, y2: point.y, viewport: PREVIEW_VIEWPORT };
    event.currentTarget.setPointerCapture(event.pointerId);
    captureDraftRef.current = draft;
    setCaptureDraft(draft);
  }

  function handleCapturePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const draft = captureDraftRef.current;
    if (!draft) return;
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const point = pointFromEvent(event.clientX, event.clientY, rect);
    const next = { ...draft, x2: point.x, y2: point.y };
    captureDraftRef.current = next;
    setCaptureDraft(next);
  }

  function handleCapturePointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    const draft = captureDraftRef.current;
    if (!draft) return;
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    const end = pointFromEvent(event.clientX, event.clientY, rect);
    const moved = Math.abs(end.x - draft.x) > 4 || Math.abs(end.y - draft.y) > 4;
    onCapturePoint?.(
      moved
        ? { ...draft, x2: end.x, y2: end.y }
        : { x: end.x, y: end.y, viewport: PREVIEW_VIEWPORT },
    );
    captureDraftRef.current = null;
    setCaptureDraft(null);
  }

  function pointFromEvent(clientX: number, clientY: number, rect: DOMRect) {
    return {
      x: clamp(Math.round(((clientX - rect.left) * PREVIEW_VIEWPORT.width) / rect.width), 0, PREVIEW_VIEWPORT.width),
      y: clamp(Math.round(((clientY - rect.top) * PREVIEW_VIEWPORT.height) / rect.height), 0, PREVIEW_VIEWPORT.height),
    };
  }

  function handleMarkerPointerDown(
    event: ReactPointerEvent<HTMLSpanElement>,
    point: RodoparMapPoint,
  ) {
    if (!pointDragEnabled) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDraggedPoint({
      key: mapPointKey(point),
      point,
      x: point.x,
      y: point.y,
      x2: point.x2,
      y2: point.y2,
    });
  }

  function handleMarkerPointerMove(event: ReactPointerEvent<HTMLSpanElement>) {
    if (!draggedPoint) return;
    event.preventDefault();
    event.stopPropagation();
    const frame = event.currentTarget.closest(".site-frame-wrap");
    if (!frame) return;
    const { x, y } = pointFromEvent(event.clientX, event.clientY, frame.getBoundingClientRect());
    setDraggedPoint((current) => {
      if (!current) return current;
      const hasEnd = typeof current.point.x2 === "number" && typeof current.point.y2 === "number";
      const x2 = hasEnd ? clamp(current.point.x2! + x - current.point.x, 0, PREVIEW_VIEWPORT.width) : null;
      const y2 = hasEnd ? clamp(current.point.y2! + y - current.point.y, 0, PREVIEW_VIEWPORT.height) : null;
      return { ...current, x, y, x2, y2 };
    });
  }

  function handleMarkerPointerUp(event: ReactPointerEvent<HTMLSpanElement>) {
    if (!draggedPoint) return;
    event.preventDefault();
    event.stopPropagation();
    const next = {
      x: draggedPoint.x,
      y: draggedPoint.y,
      x2: draggedPoint.x2,
      y2: draggedPoint.y2,
      viewport: PREVIEW_VIEWPORT,
    };
    onMoveMapPoint?.(draggedPoint.point, next);
    setDraggedPoint(null);
  }

  useEffect(() => {
    if (!run?.id || run.dry_run || !automationRunning) return;

    const currentRunId = run.id;
    const source = new EventSource(`${API_BASE}/events`);
    lastEventIdRef.current = 0;
    runPayloadRef.current = {};

    function inputValueForStep(stepData: StepDefinition, eventValue: unknown) {
      if (typeof eventValue === "string" && eventValue) return eventValue;
      const inputKey = (stepData.input_key || "").trim().toLowerCase();
      if (inputKey === "filial") return runPayloadRef.current.sample_filial || "";
      if (inputKey === "serie") return runPayloadRef.current.sample_serie || "";
      if (inputKey === "documento") return runPayloadRef.current.sample_documento || "";
      return "";
    }

    function mirrorStep(stepData: StepDefinition, eventValue: unknown) {
      if (stepData.action !== "click" && stepData.action !== "fill") return;
      const clickCommand: PreviewCommand = {
        type: "preview.click",
        x: stepData.x,
        y: stepData.y,
        viewportWidth: stepData.viewport.width,
        viewportHeight: stepData.viewport.height,
      };
      window.setTimeout(() => postPreviewCommand(clickCommand), 120);

      if (stepData.action === "fill") {
        const text = inputValueForStep(stepData, eventValue);
        if (text) {
          window.setTimeout(() => postPreviewCommand({ type: "preview.type", text }), 320);
        }
      }
    }

    source.addEventListener("automation", (event) => {
      const parsed = JSON.parse((event as MessageEvent).data) as AutomationEvent;
      if (parsed.run_id !== currentRunId || parsed.id <= lastEventIdRef.current) return;
      lastEventIdRef.current = parsed.id;
      if (
        parsed.kind === "xml_sefaz.open" || parsed.kind === "chamado_novelis.prepared" ||
        parsed.kind === "novelis.login" || parsed.kind === "novelis.open_chamado"
      ) setOwnBrowserNoticeOpen(true);
      if (isRodoparWaitEvent(parsed, currentRunId)) setManualLoginHint(true);

      if (parsed.kind === "run.started") {
        runPayloadRef.current = parsed.payload as RunStartPayload;
        if (rodoparStatusOnly || runPayloadRef.current.flow === "pdf-rodopar") {
          setVisible(false);
          setFrameTarget("");
          return;
        }
        const target = previewTargetForFlow(runPayloadRef.current.flow || run.flow, loginTarget);
        setFrameTarget(target);
        setVisible(Boolean(target));
        setFrameKey((current) => current + 1);
        return;
      }

      if (parsed.kind === "xml_sefaz.target") {
        const cteId = String(parsed.payload?.cteId || "");
        if (cteId) scheduleSefazKeyFill(cteId);
        return;
      }

      if (parsed.kind !== "step.started") return;
      if (rodoparStatusOnly) return;
      const payload = parsed.payload as StepEventPayload;
      if (!isStepDefinition(payload.step)) return;
      mirrorStep(payload.step, payload.inputValue);
    });

    return () => source.close();
  }, [automationRunning, defaultTarget, html5Target, loginTarget, rodoparStatusOnly, run?.dry_run, run?.flow, run?.id]);

  return (
    <section className="panel preview-panel">
      <div className="panel-title">
        <Globe size={18} aria-hidden="true" />
        <h2>{localStatusFlow ? "Status do fluxo" : "Preview do navegador"}</h2>
        {step ? <span className="pill">#{step.number}</span> : null}
      </div>

      {!localStatusFlow && !rodoparStatusOnly ? (
        <BrowserPreviewToolbar
          automationRunning={automationRunning}
          onAcceptBlueScreen={clickLegalNotice}
          onClose={() => setVisible(false)}
          onOpenDellmar={clickDellmarApp}
          onOpenHtml5={() => {
            setFrameTarget(html5Target);
            setVisible(true);
          }}
          onOpenRodopar={() => {
            setFrameTarget(loginTarget);
            setVisible(true);
          }}
          onRefresh={() => setFrameKey((current) => current + 1)}
          visible={visible}
        />
      ) : null}

      <div className="browser-frame-scroll">
        <div className="browser-frame">
          {localStatusFlow ? (
            <LocalFlowStatus events={events} run={run} />
          ) : rodoparStatusOnly ? (
            <RodoparStatusOnly
              automationRunning={automationRunning}
              confirmed={rodoparConfirmedSeen}
              confirming={manualLoginConfirming}
              error={manualLoginError}
              onConfirm={confirmRodoparLogin}
              runId={run?.id}
              submitted={manualLoginSubmitted}
            />
          ) : visible ? (
            <div className="site-frame-wrap">
              {liveSnapshotMode ? (
                <LiveBrowserSnapshot enabled={liveSnapshotMode} />
              ) : (
                <iframe
                  ref={iframeRef}
                  key={`${frameTarget || defaultTarget}-${frameKey}`}
                  onLoad={handleFrameLoad}
                  sandbox="allow-downloads allow-forms allow-modals allow-pointer-lock allow-popups allow-same-origin allow-scripts"
                  src={frameUrl}
                  title="Site DataPar"
                />
              )}
              {showOwnBrowserNotice ? <OwnBrowserNotice /> : null}
              {showRodoparLoginModal ? <div className="preview-modal-backdrop" aria-hidden="true" /> : null}
              {showRodoparLoginModal ? (
                <RodoparLoginGate
                  confirming={manualLoginConfirming}
                  error={manualLoginError}
                  onConfirm={confirmRodoparLogin}
                  runId={run?.id}
                />
              ) : null}
              {markerStyle ? <span className="coordinate-marker" style={markerStyle} /> : null}
              <PreviewMarkers
                displayPoints={displayPoints}
                draggedPoint={draggedPoint}
                onMarkerPointerCancel={() => setDraggedPoint(null)}
                onMarkerPointerDown={handleMarkerPointerDown}
                onMarkerPointerMove={handleMarkerPointerMove}
                onMarkerPointerUp={handleMarkerPointerUp}
                pointDragEnabled={pointDragEnabled}
                regionBoxes={regionBoxes}
                selectedMapPoint={selectedMapPoint}
              />
              {captureEnabled ? (
                <div
                  className="capture-overlay"
                  onPointerCancel={() => {
                    captureDraftRef.current = null;
                    setCaptureDraft(null);
                  }}
                  onPointerDown={handleCapturePointerDown}
                  onPointerMove={handleCapturePointerMove}
                  onPointerUp={handleCapturePointerUp}
                  role="button"
                  tabIndex={0}
                >
                  {captureDraft && typeof captureDraft.x2 === "number" ? (
                    <span className="map-region-draft" style={regionBoxStyle(captureDraft)} />
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : (
            <p className="muted">
              {simulationRun ? "Simulação não abriu navegador." : "Aguardando tela do navegador."}
            </p>
          )}
        </div>
      </div>
      <p className="muted compact">{visible ? frameUrl : "Sem URL ativa."}</p>
    </section>
  );
}
