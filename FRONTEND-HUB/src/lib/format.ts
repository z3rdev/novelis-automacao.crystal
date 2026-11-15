const dt = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
const d = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" });
const t = new Intl.DateTimeFormat("pt-BR", { timeStyle: "medium" });
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const formatDate = (s: string | null | undefined, formatter: Intl.DateTimeFormat) => {
  if (!s) return "—";
  const date = new Date(s);
  return Number.isNaN(date.getTime()) ? s : formatter.format(date);
};
export const fmtDateTime = (s?: string | null) => formatDate(s, dt);
// ISO calendar dates have no timezone. Parsing them as UTC shifts the day
// backwards in Brazil, including the displayed end date of a tariff.
export const fmtDate = (s?: string | null) => formatDate(
  s && /^\d{4}-\d{2}-\d{2}$/.test(s) ? `${s}T12:00:00` : s, d,
);
export const fmtTime = (s?: string | null) => formatDate(s, t);
export const fmtBRL = (n: number | null) => n === null ? "—" : brl.format(n);
export const fmtNum = (n: number) => n.toLocaleString("pt-BR");

/** CT-e no padrão filial-série-número, ex.: 2-10-10001 */
export const CTE_RE = /^\d{1,3}-\d{1,3}-\d{1,9}$/;

export interface ParsedCtes { validos: string[]; invalidos: string[]; duplicados: string[] }
export function parseCteList(raw: string[]): ParsedCtes {
  const seen = new Set<string>(); const validos: string[] = []; const invalidos: string[] = []; const duplicados: string[] = [];
  for (const r of raw) {
    const v = r.trim().replace(/\s+/g, "");
    if (!v) continue;
    if (!CTE_RE.test(v)) { invalidos.push(v); continue; }
    if (seen.has(v)) { if (!duplicados.includes(v)) duplicados.push(v); continue; }
    seen.add(v); validos.push(v);
  }
  return { validos, invalidos, duplicados };
}
