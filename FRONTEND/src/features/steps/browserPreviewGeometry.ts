import type { CSSProperties } from "react";

import type { RodoparMapPoint } from "../../lib/api";
import { mapPointKey } from "../mapping/mappingUtils";

export const PREVIEW_VIEWPORT = { width: 1024, height: 750, dpr: 1 };

export interface RegionBox {
  key: string;
  label: string;
  x: number;
  y: number;
  x2: number;
  y2: number;
  viewport: { width: number; height: number; dpr: number };
}

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function regionBoxStyle(region: {
  x: number;
  y: number;
  x2?: number | null;
  y2?: number | null;
  viewport: { width: number; height: number; dpr: number };
}): CSSProperties {
  const x2 = typeof region.x2 === "number" ? region.x2 : region.x;
  const y2 = typeof region.y2 === "number" ? region.y2 : region.y;
  const left = Math.min(region.x, x2);
  const top = Math.min(region.y, y2);
  return {
    height: `${(Math.abs(y2 - region.y) / region.viewport.height) * 100}%`,
    left: `${(left / region.viewport.width) * 100}%`,
    top: `${(top / region.viewport.height) * 100}%`,
    width: `${(Math.abs(x2 - region.x) / region.viewport.width) * 100}%`,
  };
}

export function buildRegionBoxes(points: RodoparMapPoint[]): RegionBox[] {
  const boxes = points.flatMap((point) =>
    point.kind === "region" && typeof point.x2 === "number" && typeof point.y2 === "number"
      ? [
          {
            key: `region:${mapPointKey(point)}`,
            label: point.id,
            x: point.x,
            y: point.y,
            x2: point.x2,
            y2: point.y2,
            viewport: point.viewport,
          },
        ]
      : [],
  );
  return [...boxes, ...buildPairedRegionBoxes(points)];
}

function buildPairedRegionBoxes(points: RodoparMapPoint[]): RegionBox[] {
  return points.flatMap((start) => {
    const match = /^P_I_(.+)$/i.exec(start.id);
    if (!match || typeof start.x2 === "number") return [];
    const end = points.find(
      (point) =>
        point.tab === start.tab &&
        (point.sub_tab ?? "") === (start.sub_tab ?? "") &&
        point.id.toLowerCase() === `p_f_${match[1]}`.toLowerCase(),
    );
    if (!end) return [];
    return [
      {
        key: `pair:${mapPointKey(start)}:${mapPointKey(end)}`,
        label: match[1],
        x: start.x,
        y: start.y,
        x2: end.x,
        y2: end.y,
        viewport: start.viewport,
      },
    ];
  });
}
