export interface PreviewCapturePoint {
  x: number;
  y: number;
  x2?: number | null;
  y2?: number | null;
  viewport: {
    width: number;
    height: number;
    dpr: number;
  };
}
