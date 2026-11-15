import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useApi } from "@/services";
import { desktop } from "@/services/desktop";
import { makeWidgetSnapshot, widgetSnapshotKey } from "@/services/status-widget";

export function StatusWidgetBridge() {
  const { api, mode, baseUrl } = useApi();
  const navigate = useNavigate();
  const native = desktop.isDesktop;
  const session = useQuery({
    queryKey: ["operator-session", mode, baseUrl],
    queryFn: () => api.getSession(),
    enabled: native && mode === "local",
    refetchInterval: 15_000,
    refetchIntervalInBackground: true,
    networkMode: "always",
    retry: 0,
  });
  const enabled = native && mode === "local" && !!session.data?.session && !session.isError;
  const run = useQuery({
    queryKey: ["run", mode, baseUrl],
    queryFn: () => api.getRun(),
    enabled,
    refetchInterval: 3_000,
    refetchIntervalInBackground: true,
    networkMode: "always",
    retry: 0,
  });
  const schedules = useQuery({
    queryKey: ["schedules", mode, baseUrl],
    queryFn: () => api.getSchedules(),
    enabled,
    refetchInterval: 5_000,
    refetchIntervalInBackground: true,
    networkMode: "always",
    retry: 0,
  });
  useEffect(() => {
    if (!native) return;
    const connection =
      mode !== "local"
        ? "demo"
        : session.isError || (enabled && (run.isError || schedules.isError))
          ? "offline"
          : !session.data
            ? "connecting"
            : !session.data.session
              ? "login_required"
              : !run.data || !schedules.data
                ? "connecting"
                : "connected";
    const checkedAt =
      connection === "connected"
        ? Math.min(session.dataUpdatedAt, run.dataUpdatedAt, schedules.dataUpdatedAt)
        : Date.now();
    const value = makeWidgetSnapshot({
      run: run.data,
      schedules: schedules.data,
      connection,
      now: checkedAt,
    });
    try {
      localStorage.setItem(widgetSnapshotKey, JSON.stringify(value));
    } catch {
      /* Next refresh retries. */
    }
  }, [
    native,
    mode,
    enabled,
    session.data,
    session.dataUpdatedAt,
    session.isError,
    run.data,
    run.dataUpdatedAt,
    run.isError,
    schedules.data,
    schedules.dataUpdatedAt,
    schedules.isError,
  ]);
  useEffect(() => {
    if (!native) return;
    let disposed = false;
    let unlisten: (() => void) | undefined;
    void desktop
      .onWidgetNavigate((page) => void navigate({ to: page }))
      .then((stop) => {
        if (disposed) stop();
        else unlisten = stop;
      });
    return () => {
      disposed = true;
      unlisten?.();
    };
  }, [native, navigate]);
  return null;
}
