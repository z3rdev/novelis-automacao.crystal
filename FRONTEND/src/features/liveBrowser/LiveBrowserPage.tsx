import { invoke } from "@tauri-apps/api/core";
import { AlertCircle, ArrowLeft, Maximize2, MonitorX } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { getBrowserState, type RunSnapshot } from "../../lib/api";
import { RodoparControlPage } from "../rodoparControl/PolicyRodoparControlPage";
import "./liveBrowser.css";

const AUTO_EMBED_POLL_MS = 1500;

function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

// Tauri command errors (Err(String) on the Rust side) reject the invoke()
// promise with the raw string itself, not a JS Error — `instanceof Error`
// is always false for them, which used to silently swallow the real
// message and fall back to a generic one.
function describeError(err: unknown, fallback: string): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string" && err.trim()) return err;
  return fallback;
}

interface Props {
  onExit: () => void;
  run: RunSnapshot | null;
}

export function LiveBrowserPage({ onExit, run }: Props) {
  const [pid, setPid] = useState<number | null>(null);
  const [embedded, setEmbedded] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const tauri = isTauri();
  const embeddedPidRef = useRef<number | null>(null);

  async function refreshPid() {
    try {
      const state = await getBrowserState();
      setPid(state.pid);
      return state.pid;
    } catch (err) {
      setError(describeError(err, "Falha ao consultar o navegador."));
      return null;
    }
  }

  useEffect(() => {
    void refreshPid();
  }, []);

  // Whenever a browser window shows up (or a new one replaces a closed one —
  // the shared automation browser gets recycled between runs), embed it
  // automatically instead of waiting for a manual click. The button stays
  // around as a fallback for recovering from a failed attempt.
  //
  // Chrome still thinks it owns its own title bar (it draws that UI itself,
  // not the OS) and lets the user drag it like any normal window — as a
  // WS_CHILD that just moves it within our Tauri window instead of the whole
  // desktop. Rather than hooking the window's message loop to block that (a
  // much bigger, riskier change), we just keep re-asserting the intended
  // position/size on every poll tick so a drag gets corrected within a
  // second or so instead of staying wherever it was dropped.
  useEffect(() => {
    if (!tauri) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      let currentPid: number | null = null;
      try {
        const state = await getBrowserState();
        currentPid = state.pid;
      } catch {
        return;
      }
      if (cancelled) return;
      setPid(currentPid);
      if (currentPid) {
        try {
          await invoke("embed_browser_window", { pid: currentPid });
          if (cancelled) return;
          embeddedPidRef.current = currentPid;
          setEmbedded(true);
          setError("");
        } catch (err) {
          if (cancelled) return;
          // The shared automation browser can close/recycle between the
          // state fetch above and this call (a new run starting, a page
          // closing) — that's routine, not a real failure, and happens
          // constantly since this loop re-embeds every tick. Surfacing it
          // as an error banner would just flash noise at the user every
          // time the browser cycles. Log it for debugging and quietly
          // treat it as "nothing to embed right now"; the manual "Embutir"
          // button still reports failures for real, deliberate attempts.
          console.debug("auto-embed: skipped this tick", describeError(err, String(err)));
          embeddedPidRef.current = null;
          setEmbedded(false);
        }
      } else if (embeddedPidRef.current) {
        embeddedPidRef.current = null;
        setEmbedded(false);
      }
    }, AUTO_EMBED_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [tauri]);

  async function handleEmbed() {
    setError("");
    setBusy(true);
    try {
      const currentPid = await refreshPid();
      if (!currentPid) {
        setError("Nenhum navegador aberto ainda. Inicie uma execução primeiro.");
        return;
      }
      await invoke("embed_browser_window", { pid: currentPid });
      embeddedPidRef.current = currentPid;
      setEmbedded(true);
    } catch (err) {
      setError(describeError(err, "Falha ao embutir a janela."));
    } finally {
      setBusy(false);
    }
  }

  async function handleUnembed() {
    if (!pid) return;
    setError("");
    setBusy(true);
    try {
      await invoke("unembed_browser_window", { pid });
      embeddedPidRef.current = null;
      setEmbedded(false);
    } catch (err) {
      setError(describeError(err, "Falha ao desembutir a janela."));
    } finally {
      setBusy(false);
    }
  }

  async function handleExit() {
    // Leaving this view swaps the React content back to the dashboard shell,
    // but a reparented native window doesn't know or care about that — it
    // would just keep sitting on screen over whatever renders next. Detach it
    // first so it goes back to being its own floating window.
    if (embedded && pid) {
      try {
        await invoke("unembed_browser_window", { pid });
      } catch {
        // best-effort — still navigate away even if this fails
      }
    }
    onExit();
  }

  if (!tauri) {
    return (
      <section className="panel live-browser-page">
        <div className="panel-title">
          <Maximize2 size={18} aria-hidden="true" />
          <h2>Navegador ao vivo</h2>
        </div>
        <p className="muted">
          Essa tela só funciona dentro do app desktop (Tauri) — no navegador comum não tem como
          embutir uma janela nativa.
        </p>
      </section>
    );
  }

  return (
    <div className="live-browser-page">
      <div className="live-browser-toolbar">
        <button className="secondary-button" disabled={busy} onClick={() => void handleExit()} type="button">
          <ArrowLeft size={16} aria-hidden="true" />
          Voltar
        </button>
        <button className="primary-button" disabled={busy} onClick={() => void handleEmbed()} type="button">
          <Maximize2 size={16} aria-hidden="true" />
          {embedded ? "Reajustar" : "Embutir navegador"}
        </button>
        <button
          className="secondary-button"
          disabled={busy || !embedded}
          onClick={() => void handleUnembed()}
          type="button"
        >
          <MonitorX size={16} aria-hidden="true" />
          Desembutir
        </button>
        <span className="live-browser-pid">{pid ? `PID ${pid}` : "Nenhum navegador aberto"}</span>
      </div>
      {error ? (
        <div className="error-banner">
          <AlertCircle size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      ) : null}
      <div className="live-browser-body">
        <div className="live-browser-slot">
          {!embedded ? (
            <p className="muted">Aguardando o navegador da automação abrir para embutir automaticamente...</p>
          ) : null}
        </div>
        <div className="live-browser-controls">
          <RodoparControlPage hideLiveView run={run} />
        </div>
      </div>
    </div>
  );
}
