import type { LogEntry, Severity } from "@/services";
import { Info, CircleCheck, TriangleAlert, CircleX, Bug } from "lucide-react";

export const logLevels = {
  info: { label: "Informação", icon: Info, color: "text-muted-foreground", background: "bg-muted" },
  sucesso: {
    label: "Sucesso",
    icon: CircleCheck,
    color: "text-success",
    background: "bg-success/10",
  },
  aviso: {
    label: "Aviso",
    icon: TriangleAlert,
    color: "text-warning-foreground",
    background: "bg-warning/10",
  },
  erro: { label: "Erro", icon: CircleX, color: "text-destructive", background: "bg-destructive/10" },
  debug: { label: "Diagnóstico", icon: Bug, color: "text-muted-foreground", background: "bg-muted" },
} satisfies Record<Severity, unknown>;

const sources: Record<string, string> = {
  run: "Execução",
  pendentes: "Execução",
  consulta: "Consulta",
  crystal_pdf: "DACTE",
  xml_sefaz: "XML · SEFAZ",
  novelis_relatorio: "Relatório Novelis",
  tariffs: "Tarifário Novelis",
  novelis: "Chamados",
  chamado_novelis: "Chamados",
  browser: "Navegador",
  captures: "Arquivos",
  scheduler: "Agendamento",
  comprovante_local: "Comprovantes",
  comprovantes: "Comprovantes",
};
export function logCategory(source: string) {
  if (source.startsWith("pendentes.sql") || source.startsWith("pendentes.manual_sql"))
    return "SQL Server";
  if (source.startsWith("pendentes.novelis_relatorio")) return "Relatório Novelis";
  if (["pendentes.plan", "pendentes.files_check"].includes(source)) return "Arquivos";
  return sources[source.split(".")[0]!] ?? "Sistema";
}

export function eventDetails(entry: LogEntry): unknown {
  if (!entry.details) return null;
  try {
    return JSON.parse(entry.details);
  } catch {
    return entry.details;
  }
}
export function eventCte(entry: LogEntry) {
  const data = eventDetails(entry);
  if (!data || typeof data !== "object" || !("cte" in data)) return null;
  return typeof data.cte === "string" && /^\d+-\d+-\d+$/.test(data.cte) ? data.cte : null;
}
export function eventMessage(entry: LogEntry) {
  if (["erro", "aviso"].includes(entry.severity)) return entry.message;
  return (
    (
      {
        "xml_sefaz.saved": "XML salvo.",
        "crystal_pdf.saved": "DACTE salvo.",
        "xml_sefaz.target": "Preparando consulta do XML.",
      } as Record<string, string>
    )[entry.source] ?? entry.message
  );
}

const privateField =
  /(?:pass(?:word|phrase)?|senha|secret|token|pidkey|authorization|credential|private.?key)/i;
export function safeEventDetails(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(safeEventDetails);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        privateField.test(key) ? "[oculto]" : safeEventDetails(item),
      ]),
    );
  return value;
}
