import { Crosshair, MousePointerClick, Move, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { MapPointKind, RodoparMapPoint } from "../../lib/api";
import type { PreviewCapturePoint } from "./mappingTypes";
import { sameMapScope } from "./mappingUtils";
import "./mapping.css";

interface Props {
  captureEnabled: boolean;
  capturedPoint: PreviewCapturePoint | null;
  dragEnabled: boolean;
  points: RodoparMapPoint[];
  selectedPoint: RodoparMapPoint | null;
  selectedSubTab: string;
  selectedTab: string;
  onCaptureChange: (enabled: boolean) => void;
  onClearCapture: () => void;
  onDragChange: (enabled: boolean) => void;
  onDelete: (point: RodoparMapPoint) => Promise<void>;
  onSave: (point: RodoparMapPoint) => Promise<void>;
  onSelectPoint: (point: RodoparMapPoint | null) => void;
}

export function MapperPanel({
  captureEnabled,
  capturedPoint,
  dragEnabled,
  points,
  selectedPoint,
  selectedSubTab,
  selectedTab,
  onCaptureChange,
  onClearCapture,
  onDragChange,
  onDelete,
  onSave,
  onSelectPoint,
}: Props) {
  const [fieldId, setFieldId] = useState("");
  const [kind, setKind] = useState<MapPointKind>("field");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const tabPoints = useMemo(
    () => points.filter((point) => sameMapScope(point.tab, point.sub_tab, selectedTab, selectedSubTab)),
    [points, selectedSubTab, selectedTab],
  );

  useEffect(() => {
    if (!selectedPoint) return;
    setFieldId(selectedPoint.id);
    setKind(selectedPoint.kind);
    setDescription(selectedPoint.description || "");
  }, [selectedPoint]);

  async function handleSave() {
    setError("");
    const id = fieldId.trim();
    if (!id) {
      setError("Informe o ID do ponto.");
      return;
    }
    const basePoint = capturedPoint ?? selectedPoint;
    if (!basePoint) {
      setError("Ative captura e clique no preview para gravar coordenada.");
      return;
    }

    const point: RodoparMapPoint = {
      id,
      tab: selectedTab,
      sub_tab: selectedSubTab,
      kind,
      x: basePoint.x,
      y: basePoint.y,
      x2: kind === "region" ? basePoint.x2 ?? null : null,
      y2: kind === "region" ? basePoint.y2 ?? null : null,
      viewport: basePoint.viewport,
      description: description.trim(),
    };

    setBusy(true);
    try {
      await onSave(point);
      onClearCapture();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar ponto.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!selectedPoint) return;
    setBusy(true);
    setError("");
    try {
      await onDelete(selectedPoint);
      setFieldId("");
      setDescription("");
      onClearCapture();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao excluir ponto.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel mapper-panel">
      <div className="panel-title">
        <Crosshair size={18} aria-hidden="true" />
        <h2>Pontos</h2>
        <span className="pill">{points.length}</span>
      </div>

      <div className="mapper-grid">
        <label className="field">
          <span>Tipo</span>
          <select value={kind} onChange={(event) => setKind(event.target.value as MapPointKind)}>
            <option value="field">Campo</option>
            <option value="button">Botão</option>
            <option value="tab">Aba</option>
            <option value="region">Região</option>
            <option value="other">Outro</option>
          </select>
        </label>
        <label className="field">
          <span>ID do ponto</span>
          <input
            placeholder="ex: geral.numero_ctrc"
            value={fieldId}
            onChange={(event) => setFieldId(event.target.value)}
          />
        </label>
        <label className="field wide">
          <span>Descrição</span>
          <input
            placeholder="opcional"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
      </div>

      <div className="mapper-status">
        <span>{formatPointStatus(capturedPoint, selectedPoint)}</span>
        <span>{selectedSubTab ? `${selectedTab} / ${selectedSubTab}` : selectedTab}</span>
      </div>

      {error ? <p className="error-text">{error}</p> : null}

      <div className="button-row">
        <button
          className={captureEnabled ? "primary-button" : "secondary-button"}
          onClick={() => onCaptureChange(!captureEnabled)}
          type="button"
        >
          <MousePointerClick size={16} aria-hidden="true" />
          Capturar
        </button>
        <button
          className={dragEnabled ? "primary-button" : "secondary-button"}
          disabled={!tabPoints.length}
          onClick={() => onDragChange(!dragEnabled)}
          type="button"
        >
          <Move size={16} aria-hidden="true" />
          Clicar e arrastar
        </button>
        <button className="primary-button" disabled={busy} onClick={handleSave} type="button">
          <Save size={16} aria-hidden="true" />
          Salvar
        </button>
        <button
          className="icon-button"
          disabled={!selectedPoint || busy}
          onClick={handleDelete}
          title="Excluir ponto"
          type="button"
        >
          <Trash2 size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="map-point-list">
        <div className="map-point-heading">
          <strong>{selectedTab}</strong>
          <span>{tabPoints.length} ponto(s)</span>
        </div>
        {tabPoints.map((point) => (
          <button
            className={
              selectedPoint?.tab === point.tab &&
              (selectedPoint?.sub_tab ?? "") === (point.sub_tab ?? "") &&
              selectedPoint?.id === point.id
                ? "map-point-row selected"
                : "map-point-row"
            }
            key={`${point.tab}:${point.sub_tab ?? ""}:${point.id}`}
            onClick={() => onSelectPoint(point)}
            type="button"
          >
            <strong>{point.id}</strong>
            <span>{formatPointRow(point)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function formatPointStatus(
  capturedPoint: PreviewCapturePoint | null,
  selectedPoint: RodoparMapPoint | null,
) {
  const point = capturedPoint ?? selectedPoint;
  if (!point) return "x: - y: -";
  const end =
    typeof point.x2 === "number" && typeof point.y2 === "number"
      ? ` -> x2: ${point.x2} y2: ${point.y2}`
      : "";
  return `x: ${point.x} y: ${point.y}${end}`;
}

function formatPointRow(point: RodoparMapPoint) {
  if (point.kind === "region" && typeof point.x2 === "number" && typeof point.y2 === "number") {
    return `${point.kind} - ${point.x},${point.y} -> ${point.x2},${point.y2}`;
  }
  return `${point.kind} - ${point.x},${point.y}`;
}
