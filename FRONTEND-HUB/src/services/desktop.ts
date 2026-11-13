// Recursos nativos isolados da interface e dos servicos HTTP.
export interface DesktopBridge {
  isDesktop: boolean;
  openPath(path: string): Promise<void>;
  pickFolder(): Promise<string | null>;
  saveFile(name: string, data: Blob): Promise<void>;
}

function isTauri() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export const desktop: DesktopBridge = {
  get isDesktop() {
    return isTauri();
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
    return await (await import("@tauri-apps/plugin-dialog")).open({ directory: true, multiple: false });
  },
  async saveFile(name, data) {
    if (isTauri()) {
      const path = await (await import("@tauri-apps/plugin-dialog")).save({ defaultPath: name });
      if (path) await (await import("@tauri-apps/plugin-fs")).writeFile(path, new Uint8Array(await data.arrayBuffer()));
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
