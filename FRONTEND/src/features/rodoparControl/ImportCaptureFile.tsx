import { Upload } from "lucide-react";
import { useRef, useState } from "react";

import { importCaptureFile } from "../../lib/api";

const DEFAULT_PATH = "captures/rodopar-download-pdfs-pointer-map.json";

export function ImportCaptureFile() {
  const [path, setPath] = useState(DEFAULT_PATH);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    setStatus("");
    setBusy(true);
    try {
      const text = await file.text();
      let parsed: unknown;
      try {
        parsed = JSON.parse(text);
      } catch {
        throw new Error("Esse arquivo não é um JSON válido.");
      }
      if (typeof parsed !== "object" || parsed === null || !Array.isArray((parsed as { points?: unknown }).points)) {
        throw new Error('O JSON precisa ter uma lista "points" (mapa de passos do Rodopar).');
      }
      const result = await importCaptureFile(path.trim() || DEFAULT_PATH, parsed);
      setStatus(`Importado: ${result.totalPoints} passo(s) gravados em ${result.path}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao importar o arquivo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rodopar-import">
      <div className="rodopar-import-title">
        <Upload size={16} aria-hidden="true" />
        <span>Importar mapa (JSON)</span>
      </div>
      <p className="muted compact">
        Substitui o arquivo de captura pelo JSON escolhido. Se uma execução já estiver rodando com esse mapa
        carregado, só vale a partir da próxima execução.
      </p>
      <input
        className="rodopar-control-input"
        onChange={(event) => setPath(event.target.value)}
        placeholder="Caminho do arquivo de captura"
        value={path}
      />
      <button disabled={busy} onClick={() => fileInputRef.current?.click()} type="button">
        {busy ? "Importando..." : "Escolher arquivo .json"}
      </button>
      <input accept=".json" hidden onChange={handleFile} ref={fileInputRef} type="file" />
      {status ? <p className="rodopar-import-status ok">{status}</p> : null}
      {error ? <p className="rodopar-import-status error">{error}</p> : null}
    </div>
  );
}
