import { AlertTriangle, CheckCircle2, ClipboardList, FileCheck2, FolderSearch } from "lucide-react";

import type { AutomationEvent, RunSnapshot } from "../../lib/api";

interface Props {
  events: AutomationEvent[];
  run: RunSnapshot | null;
}

interface CopiedFile {
  cte?: string;
  source?: string;
  target?: string;
}

function text(value: unknown) {
  return typeof value === "string" ? value : "";
}

function numberValue(value: unknown) {
  return typeof value === "number" ? value : 0;
}

function listValue(value: unknown) {
  return Array.isArray(value) ? value : [];
}

function fileName(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() || path;
}

export function LocalFlowStatus({ events, run }: Props) {
  const runEvents = events.filter((event) => event.run_id === run?.id);
  const completed = runEvents.find((event) => event.kind === "comprovante_local.completed");
  const started = runEvents.find((event) => event.kind === "comprovante_local.started");
  const runStarted = runEvents.find((event) => event.kind === "run.started");
  const latest = runEvents[0];
  const payload = completed?.payload ?? {};
  const sourceDir = text(payload.sourceDir) || text(started?.payload.sourceDir);
  const targetDir = text(payload.targetDir);
  const missing = listValue(payload.missing);
  const files = listValue(payload.files) as CopiedFile[];
  const cte = text(runStarted?.payload.sample_cte) || text(files[0]?.cte);
  const checked = numberValue(payload.checked);
  const found = numberValue(payload.found);
  const status = run?.status ?? "idle";

  return (
    <div style={{ display: "grid", gap: 14, padding: 24 }}>
      <div style={{ alignItems: "center", display: "flex", gap: 10 }}>
        <FolderSearch size={26} color="#09cc09" aria-hidden="true" />
        <div>
          <h3 style={{ margin: 0 }}>Comprovante - Local</h3>
          <p className="muted compact" style={{ margin: "2px 0 0" }}>
            Busca local de comprovantes sem navegador web.
          </p>
        </div>
        <span className={status === "failed" ? "pill warn" : status === "completed" ? "pill ok" : "pill"}>
          {status}
        </span>
      </div>

      <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
        <Metric label="CTE" value={cte || "-"} />
        <Metric label="Verificados" value={String(checked || "-")} />
        <Metric label="Encontrados" value={String(found || "-")} />
        <Metric label="Faltantes" value={String(missing.length || 0)} />
      </div>

      <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
        <PathBox label="Origem" value={sourceDir || "Aguardando leitura da pasta."} />
        <PathBox label="Destino" value={targetDir || "Aguardando destino."} />
      </div>

      <section style={boxStyle}>
        <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
          <ClipboardList size={18} aria-hidden="true" />
          <strong>Etapa atual</strong>
        </div>
        <p style={{ margin: "8px 0 0" }}>{latest?.message || run?.message || "Aguardando execução."}</p>
      </section>

      <section style={boxStyle}>
        <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
          <FileCheck2 size={18} aria-hidden="true" />
          <strong>Arquivos</strong>
        </div>
        {files.length ? (
          <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
            {files.slice(0, 6).map((file, index) => (
              <div key={`${file.target}-${index}`} style={fileRowStyle}>
                <CheckCircle2 size={16} color="#059669" aria-hidden="true" />
                <span>{fileName(text(file.target) || text(file.source))}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted compact" style={{ margin: "8px 0 0" }}>
            Nenhum arquivo copiado ainda.
          </p>
        )}
      </section>

      {missing.length ? (
        <section style={{ ...boxStyle, borderColor: "#fed7aa" }}>
          <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
            <AlertTriangle size={18} color="#c2410c" aria-hidden="true" />
            <strong>Sem comprovante</strong>
          </div>
          <p style={{ margin: "8px 0 0" }}>{missing.join(", ")}</p>
        </section>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={boxStyle}>
      <span className="muted compact">{label}</span>
      <strong style={{ display: "block", marginTop: 4, overflowWrap: "anywhere" }}>{value}</strong>
    </div>
  );
}

function PathBox({ label, value }: { label: string; value: string }) {
  return (
    <div style={boxStyle}>
      <span className="muted compact">{label}</span>
      <p style={{ margin: "4px 0 0", overflowWrap: "anywhere" }}>{value}</p>
    </div>
  );
}

const boxStyle = {
  background: "#ffffff",
  border: "1px solid #d8e2ef",
  borderRadius: 8,
  padding: 12,
} as const;

const fileRowStyle = {
  alignItems: "center",
  background: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: 6,
  display: "flex",
  gap: 8,
  padding: "8px 10px",
} as const;
