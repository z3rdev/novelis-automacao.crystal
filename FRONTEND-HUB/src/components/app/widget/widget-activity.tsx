import { widgetMotion, widgetStatus, type WidgetSnapshot } from "@/services/status-widget";
import { FluentIcon, type FluentIconName } from "../fluent-icon";
import "./widget-activity.css";

const icons: Record<ReturnType<typeof widgetMotion>, FluentIconName> = {
  download: "download",
  generate: "settings",
  verify: "search",
  validate: "check",
  send: "forward",
  error: "warning",
  success: "check",
  connect: "refresh",
  wait: "clock",
  stop: "pause",
  locked: "lock",
};

export function WidgetActivity({
  snapshot,
  now,
}: {
  snapshot: WidgetSnapshot | null;
  now: number;
}) {
  const status = widgetStatus(snapshot, now);
  const motion = widgetMotion(snapshot, now);
  return (
    <div
      className="status-widget-current"
      data-tone={status.tone}
      data-motion={motion}
      role="status"
    >
      <span key={motion} className="widget-activity-icon">
        <FluentIcon name={icons[motion]} />
      </span>
      <h1 key={status.label} title={status.label} className="widget-activity-title">
        {status.label}
      </h1>
      <span className="widget-activity-track" aria-hidden="true">
        <span />
      </span>
    </div>
  );
}
