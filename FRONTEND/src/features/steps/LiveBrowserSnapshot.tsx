import { useEffect, useState } from "react";

import { getBrowserScreenshot } from "../../lib/api";

interface Props {
  enabled: boolean;
}

const LIVE_POLL_MS = 250;
const ERROR_POLL_MS = 800;

export function LiveBrowserSnapshot({ enabled }: Props) {
  const [image, setImage] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!enabled) {
      setImage("");
      setUrl("");
      setError("");
      return;
    }

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
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Falha ao capturar navegador.");
        }
      }
      if (!cancelled) timer = window.setTimeout(poll, nextPollMs);
    }
    void poll();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [enabled]);

  if (image) {
    return <img alt={url || "Navegador da automação"} className="live-browser-image" src={image} />;
  }

  return (
    <div className="live-browser-empty">
      <span>{error || "Aguardando captura do navegador."}</span>
    </div>
  );
}
