import type { PointerEvent as ReactPointerEvent } from "react";

import type { RodoparMapPoint } from "../../lib/api";
import { mapPointKey } from "../mapping/mappingUtils";
import type { RegionBox } from "./browserPreviewGeometry";
import { regionBoxStyle } from "./browserPreviewGeometry";

export interface PreviewDraggedPoint {
  key: string;
  point: RodoparMapPoint;
  x: number;
  y: number;
  x2?: number | null;
  y2?: number | null;
}

interface Props {
  displayPoints: RodoparMapPoint[];
  draggedPoint: PreviewDraggedPoint | null;
  pointDragEnabled: boolean;
  regionBoxes: RegionBox[];
  selectedMapPoint: RodoparMapPoint | null;
  onMarkerPointerCancel: () => void;
  onMarkerPointerDown: (
    event: ReactPointerEvent<HTMLSpanElement>,
    point: RodoparMapPoint,
  ) => void;
  onMarkerPointerMove: (event: ReactPointerEvent<HTMLSpanElement>) => void;
  onMarkerPointerUp: (event: ReactPointerEvent<HTMLSpanElement>) => void;
}

export function PreviewMarkers({
  displayPoints,
  draggedPoint,
  pointDragEnabled,
  regionBoxes,
  selectedMapPoint,
  onMarkerPointerCancel,
  onMarkerPointerDown,
  onMarkerPointerMove,
  onMarkerPointerUp,
}: Props) {
  return (
    <>
      {regionBoxes.map((box) => (
        <span
          className="map-region-box"
          key={box.key}
          style={regionBoxStyle(box)}
          title={box.label}
        >
          <span>{box.label}</span>
        </span>
      ))}
      {displayPoints.map((point) => {
        const pointKey = mapPointKey(point);
        const selected =
          selectedMapPoint?.id === point.id &&
          selectedMapPoint?.tab === point.tab &&
          (selectedMapPoint?.sub_tab ?? "") === (point.sub_tab ?? "");
        const x = draggedPoint?.key === pointKey ? draggedPoint.x : point.x;
        const y = draggedPoint?.key === pointKey ? draggedPoint.y : point.y;
        return (
          <span
            className={`${selected ? "map-marker selected" : "map-marker"} ${
              pointDragEnabled ? "draggable" : "locked"
            }`}
            key={pointKey}
            onPointerCancel={onMarkerPointerCancel}
            onPointerDown={(event) => onMarkerPointerDown(event, point)}
            onPointerMove={onMarkerPointerMove}
            onPointerUp={onMarkerPointerUp}
            style={{
              left: `${(x / point.viewport.width) * 100}%`,
              top: `${(y / point.viewport.height) * 100}%`,
            }}
            title={markerTitle(point, pointDragEnabled)}
          >
            <span>{point.id}</span>
          </span>
        );
      })}
    </>
  );
}

function markerTitle(point: RodoparMapPoint, pointDragEnabled: boolean) {
  if (!pointDragEnabled) return "Ative Clicar e arrastar para mover este ponto";
  return `${point.tab}${point.sub_tab ? ` / ${point.sub_tab}` : ""} / ${point.id}`;
}
