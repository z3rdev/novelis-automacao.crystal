import { useEffect, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";

import { getBrowserScreenshot, type OverlayPoint } from "../../lib/api";

interface Props {
  capturing: boolean;
  currentStep: number | null;
  points: OverlayPoint[];
  onCapture: (x: number, y: number) => void;
}

const LIVE_POLL_MS = 300;
const ERROR_POLL_MS = 800;

export function RodoparControlLiveView({ capturing, currentStep, points, onCapture }: Props) {
  const [image, setImage] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });
  const imgRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    async function poll() {
      let nextPollMs = LIVE_POLL_MS;
      try {
        const snapshot = await getBrowserScreenshot();
        if (!cancelled) {
          setImage(snapshot.image);
          setUrl(snapshot.url);
          setError("");
        }
      } catch (err) {
        nextPollMs = ERROR_POLL_MS;
        if (!cancelled) setError(err instanceof Error ? err.message : "Falha ao capturar navegador.");
      }
      if (!cancelled) timer = window.setTimeout(poll, nextPollMs);
    }
    void poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  function handleLoad() {
    const img = imgRef.current;
    if (img) setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight });
  }

  function handleClick(event: ReactMouseEvent<HTMLImageElement>) {
    if (!capturing) return;
    const img = imgRef.current;
    if (!img || !img.naturalWidth || !img.naturalHeight) return;
    const rect = img.getBoundingClientRect();
    const x = Math.round(((event.clientX - rect.left) / rect.width) * img.naturalWidth);
    const y = Math.round(((event.clientY - rect.top) / rect.height) * img.naturalHeight);
    onCapture(clampCoord(x, img.naturalWidth), clampCoord(y, img.naturalHeight));
  }

  if (!image) {
    return (
      <div className="rodopar-control-live-empty">
        <span>{error || "Aguardando captura do navegador."}</span>
      </div>
    );
  }

  const width = naturalSize.width || 1;
  const height = naturalSize.height || 1;

  return (
    <div className={capturing ? "rodopar-control-live capturing" : "rodopar-control-live"}>
      <img
        alt={url || "Navegador da automação"}
        className="rodopar-control-live-image"
        onClick={handleClick}
        onLoad={handleLoad}
        ref={imgRef}
        src={image}
      />
      {capturing ? <div className="rodopar-control-hint">Clique no ponto desejado na tela.</div> : null}
      <div className="rodopar-control-markers">
        {points
          .filter((point) => !point.shortcut)
          .map((point) => {
            const isCurrent = point.step === currentStep;
            const classes = ["rodopar-control-marker"];
            if (point.hasTemplate) classes.push("templated");
            if (point.loopPoint) classes.push("loop");
            classes.push(isCurrent ? "current" : "dot");
            return (
              <span
                className={classes.join(" ")}
                key={point.step}
                style={{ left: `${(point.x / width) * 100}%`, top: `${(point.y / height) * 100}%` }}
                title={`${point.step} - ${point.label}${point.hasTemplate ? " (template ok)" : " (sem template)"}`}
              >
                {isCurrent ? point.step : ""}
              </span>
            );
          })}
      </div>
    </div>
  );
}

function clampCoord(value: number, max: number) {
  return Math.min(max, Math.max(0, value));
}
