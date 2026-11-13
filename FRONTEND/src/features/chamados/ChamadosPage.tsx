import { ClipboardList, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getChamados, type ChamadoRow, type ChamadosPayload } from "../../lib/api";
import "./chamados.css";

export function ChamadosPage() {
  const [payload, setPayload] = useState<ChamadosPayload | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setPayload(await getChamados());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar chamados.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    const source = payload?.rows ?? [];
    if (!text) return source;
    return source.filter((row) =>
      [
        row.cte,
        row.chamado,
        row.aberturaNovelis,
        row.idTarifario,
        row.jda,
        row.andamento,
        row.responsavel,
        row.origem,
        row.destino,
      ]
        .join(" ")
        .toLowerCase()
        .includes(text),
    );
  }, [payload?.rows, query]);
  const isReportOnly = payload?.sourceKind === "relatorio";

  return (
    <section className="panel chamados-page">
      <div className="chamados-header">
        <div>
          <div className="panel-title chamados-title">
            <ClipboardList size={18} aria-hidden="true" />
            <h2>Chamados Novelis</h2>
          </div>
          <p>Lista preenchida pelo relatório Novelis.</p>
        </div>
        <button className="icon-text-button" disabled={loading} onClick={load} type="button">
          <RefreshCw size={16} aria-hidden="true" />
          Atualizar
        </button>
      </div>

      <div className="chamados-summary">
        <SummaryCard label={isReportOnly ? "Relatório" : "Total"} value={payload?.total ?? 0} />
        <SummaryCard label="Fila" value={payload?.queueTotal ?? payload?.total ?? 0} />
        <SummaryCard label="Solucionados" value={payload?.solucionados ?? 0} tone="ok" />
        <SummaryCard label="Pendentes" value={payload?.pendentes ?? 0} tone="warn" />
        <SummaryCard label="Visíveis" value={rows.length} />
      </div>

      <div className="chamados-toolbar">
        <label className="chamados-search">
          <Search size={16} aria-hidden="true" />
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar CTE, chamado, origem, destino..."
            value={query}
          />
        </label>
        <span>{formatGeneratedAt(payload?.generatedAt)}</span>
      </div>

      {error ? <div className="chamados-error">{error}</div> : null}

      <div className="chamados-table-wrap">
        <table className="chamados-table">
          <thead>
            <tr>
              <th aria-label="Selecionar">
                <input type="checkbox" />
              </th>
              <th>CTE</th>
              <th>Data</th>
              <th>VLR Total</th>
              <th>Abertura Novelis</th>
              <th>ID Tarifário</th>
              <th>Chamado</th>
              <th>JDA</th>
              <th>Andamento</th>
              <th>Responsável</th>
              <th>Origem</th>
              <th>Destino</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={12}>Carregando chamados...</td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={12}>Nenhum chamado encontrado no JSON.</td>
              </tr>
            ) : (
              rows.map((row) => <ChamadoTableRow key={row.id} row={row} />)
            )}
          </tbody>
        </table>
      </div>

      <div className="chamados-source">{payload?.sourceFile || "Fonte JSON não encontrada."}</div>
    </section>
  );
}

function ChamadoTableRow({ row }: { row: ChamadoRow }) {
  return (
    <tr>
      <td>
        <input type="checkbox" />
      </td>
      <td>{row.cte || "-"}</td>
      <td>{formatDate(row.data)}</td>
      <td>{formatCurrency(row.vlrTotal)}</td>
      <td>
        <span className={row.aberturaNovelis === "SOLUCIONADO" ? "status-chip ok" : "status-chip warn"}>
          {row.aberturaNovelis || "-"}
        </span>
      </td>
      <td>{row.idTarifario || "-"}</td>
      <td>
        <strong>{row.chamado || "-"}</strong>
      </td>
      <td>{row.jda || "-"}</td>
      <td>{row.andamento || "-"}</td>
      <td>{row.responsavel || "-"}</td>
      <td>{row.origem || "-"}</td>
      <td>{row.destino || "-"}</td>
    </tr>
  );
}

function SummaryCard({ label, value, tone = "" }: { label: string; value: number; tone?: string }) {
  return (
    <article className={`chamados-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function formatCurrency(value: number | null) {
  if (typeof value !== "number") return "-";
  return value.toLocaleString("pt-BR", { currency: "BRL", style: "currency" });
}

function formatDate(value: string) {
  if (!value) return "-";
  const parsed = new Date(value);
  // Report-sourced rows arrive already as "DD/MM/AAAA HH:mm:ss" (Brazilian
  // format) -- `Date` only reliably parses ISO-ish strings, so this throws
  // for those (day > 12 reads as an invalid month) and used to fall back to
  // just the date half, silently dropping the opening time. Since that
  // fallback string is already in the exact format we want to show, just
  // display it as-is instead of truncating it.
  if (!Number.isNaN(parsed.getTime())) return parsed.toLocaleString("pt-BR");
  return value;
}

function formatGeneratedAt(value?: string | null) {
  if (!value) return "Sem atualização registrada.";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return `Atualizado em ${parsed.toLocaleString("pt-BR")}`;
}
