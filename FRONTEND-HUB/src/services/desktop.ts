// Recursos nativos isolados da interface e dos servicos HTTP.
import type { DeviceIdentity } from "./types";
import { classifyComputerName } from "./device-classification";
import type { NetworkStatus } from "./network-status";
export interface DesktopBridge {
  isDesktop: boolean;
  deviceIdentity(): Promise<DeviceIdentity | null>;
  networkStatus(): Promise<NetworkStatus>;
  startupEnabled(): Promise<boolean>;
  setStartup(enabled: boolean): Promise<boolean>;
  hideToTray(): Promise<void>;
  isWidgetWindow(): Promise<boolean>;
  widgetEnabled(): Promise<boolean>;
  setWidgetEnabled(enabled: boolean): Promise<boolean>;
  showStatusWidget(): Promise<void>;
  dismissStatusWidget(): Promise<void>;
  setWidgetCompact(compact: boolean): Promise<void>;
  dragStatusWidget(): Promise<void>;
  openMainFromWidget(page: "/monitor" | "/agendamentos" | "/conversas"): Promise<void>;
  onWidgetNavigate(
    listener: (page: "/monitor" | "/agendamentos" | "/conversas") => void,
  ): Promise<() => void>;
  playNotificationSound(): Promise<void>;
  setTheme(theme: "light" | "dark" | null): Promise<void>;
  openPath(path: string): Promise<void>;
  pickFolder(): Promise<string | null>;
  pickInstaller(): Promise<string | null>;
  saveFile(name: string, data: Blob): Promise<void>;
}

function isTauri() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export const desktop: DesktopBridge = {
  get isDesktop() {
    return isTauri();
  },
  async deviceIdentity() {
    if (!isTauri()) return null;
    const identity = await (
      await import("@tauri-apps/api/core")
    ).invoke<DeviceIdentity>("device_identity");
    return { ...identity, classification: classifyComputerName(identity.computer_name) };
  },
  async startupEnabled() {
    if (!isTauri()) return false;
    return await (await import("@tauri-apps/api/core")).invoke<boolean>("startup_enabled");
  },
  async networkStatus() {
    if (!isTauri()) return { kind: "unknown", transport: null };
    return await (await import("@tauri-apps/api/core")).invoke<NetworkStatus>("network_status");
  },
  async setStartup(enabled) {
    if (!isTauri())
      throw new Error("A inicialização com o Windows está disponível no aplicativo instalado.");
    return await (await import("@tauri-apps/api/core")).invoke<boolean>("set_startup", { enabled });
  },
  async hideToTray() {
    if (!isTauri()) return;
    await (await import("@tauri-apps/api/core")).invoke("hide_to_tray");
  },
  async setTheme(theme) {
    if (!isTauri()) return;
    await (await import("@tauri-apps/api/window")).getCurrentWindow().setTheme(theme);
  },
  async isWidgetWindow() {
    return (
      isTauri() &&
      (await import("@tauri-apps/api/window")).getCurrentWindow().label === "status-widget"
    );
  },
  async widgetEnabled() {
    if (!isTauri()) return false;
    return await (await import("@tauri-apps/api/core")).invoke<boolean>("widget_enabled");
  },
  async setWidgetEnabled(enabled) {
    return await (
      await import("@tauri-apps/api/core")
    ).invoke<boolean>("set_widget_enabled", { enabled });
  },
  async showStatusWidget() {
    await (await import("@tauri-apps/api/core")).invoke("show_status_widget");
  },
  async dismissStatusWidget() {
    if (!isTauri()) return;
    await (await import("@tauri-apps/api/core")).invoke("dismiss_status_widget");
  },
  async setWidgetCompact(compact) {
    if (!isTauri()) return;
    await (await import("@tauri-apps/api/core")).invoke("set_widget_compact", { compact });
  },
  async dragStatusWidget() {
    if (!isTauri()) return;
    await (await import("@tauri-apps/api/window")).getCurrentWindow().startDragging();
  },
  async openMainFromWidget(page) {
    if (!isTauri()) {
      window.location.href = `/#${page}`;
      return;
    }
    await (await import("@tauri-apps/api/core")).invoke("open_main_from_widget", { page });
  },
  async playNotificationSound() {
    if (isTauri()) await (await import("@tauri-apps/api/core")).invoke("play_notification_sound");
  },
  async onWidgetNavigate(listener) {
    if (!isTauri()) return () => {};
    return await (
      await import("@tauri-apps/api/event")
    ).listen<string>("status-widget:navigate", ({ payload }) => {
      if (payload === "/monitor" || payload === "/agendamentos" || payload === "/conversas")
        listener(payload);
    });
  },
  async openPath(path) {
    if (/^https?:\/\//.test(path)) {
      if (isTauri()) await (await import("@tauri-apps/plugin-opener")).openUrl(path);
      else window.open(path, "_blank", "noopener,noreferrer");
      return;
    }
    if (!isTauri()) {
      console.info("[desktop] abrir caminho (somente no app desktop):", path);
      return;
    }
    await (await import("@tauri-apps/plugin-opener")).openPath(path);
  },
  async pickFolder() {
    if (!isTauri()) return window.prompt("Informe o caminho da pasta:") || null;
    return await (
      await import("@tauri-apps/plugin-dialog")
    ).open({ directory: true, multiple: false });
  },
  async pickInstaller() {
    if (!isTauri()) return window.prompt("Caminho local do instalador Cargo Hub (.exe):") || null;
    return await (
      await import("@tauri-apps/plugin-dialog")
    ).open({
      directory: false,
      multiple: false,
      title: "Selecionar instalador Cargo Hub",
      filters: [{ name: "Instalador Cargo Hub", extensions: ["exe"] }],
    });
  },
  async saveFile(name, data) {
    if (isTauri()) {
      const path = await (await import("@tauri-apps/plugin-dialog")).save({ defaultPath: name });
      if (path)
        await (
          await import("@tauri-apps/plugin-fs")
        ).writeFile(path, new Uint8Array(await data.arrayBuffer()));
      return;
    }
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  },
};
