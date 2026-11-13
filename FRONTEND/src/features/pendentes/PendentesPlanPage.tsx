import { ClipboardList, Download, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { API_BASE, getPendentesPlan, type PendentesPlanPayload, type PendentesPlanRow } from "../../lib/api";
import "./pendentesPlan.css";

export function PendentesPlanPage() {
  const [payload, setPayload] = useState<PendentesPlanPayload | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exportModalOpen, setExportModalOpen] = useState(false);

  async function load() {
    setError("");
    try {
      setPayload(await getPendentesPlan());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar a lista de pendentes.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function exportPlan(scope: "todos" | "faltantes") {
    window.location.href = `${API_BASE}/pendentes/plan/export.xlsx?scope=${scope}`;
    setExportModalOpen(false);
  }

  const rows = useMemo(() => {
    const text = query.trim().toLowerCase();
    const source = payload?.rows ?? [];
    if (!text) return source;
    return source.filter((row) => [row.cte, row.filial, row.serie, row.documento].join(" ").toLowerCase().includes(text));
  }, [payload?.rows, query]);

  return (
    <section className="panel pendentes-plan-page">
      <div className="pendentes-plan-header">
        <div>
          <div className="panel-title pendentes-plan-title">
            <ClipboardList size={18} aria-hidden="true" />
            <h2>CTEs pendentes</h2>
          </div>
          <p>CTEs que ainda faltam PDF, XML, comprovante ou chamado — os que "Iniciar automação" vai processar.</p>
        </div>
        <div className="pendentes-plan-header-actions">
          <button className="icon-text-button" disabled={loading} onClick={load} type="button">
            <RefreshCw size={16} aria-hidden="true" />
            Atualizar
          </button>
          <button className="icon-text-button" onClick={() => setExportModalOpen(true)} type="button">
            <Download size={16} aria-hidden="true" />
            Exportar XLSX
          </button>
        </div>
      </div>

      {exportModalOpen ? (
        <div
          aria-labelledby="pendentes-export-modal-title"
          aria-modal="true"
          className="pendentes-export-modal-backdrop"
          onClick={() => setExportModalOpen(false)}
          role="dialog"
        >
          <div className="pendentes-export-modal" onClick={(event) => event.stopPropagation()}>
            <strong id="pendentes-export-modal-title">O que exportar?</strong>
            <p>Escolha se o XLSX deve trazer todos os CTEs ou só os que ainda faltam algo.</p>
            <div className="pendentes-export-modal-actions">
              <button className="icon-text-button" onClick={() => exportPlan("todos")} type="button">
                Tudo ({payload?.total ?? 0})
              </button>
              <button className="icon-text-button primary" onClick={() => exportPlan("faltantes")} type="button">
                Apenas faltantes ({rows.filter((row) => !row.prontoChamado).length})
              </button>
            </div>
            <button className="pendentes-export-modal-cancel" onClick={() => setExportModalOpen(false)} type="button">
              Cancelar
            </button>
          </div>
        </div>
      ) : null}

      <div className="pendentes-plan-summary">
        <SummaryCard label="Total" value={payload?.total ?? 0} />
        <SummaryCard label="Faltando PDF" tone="warn" value={payload?.faltandoPdfCount ?? 0} />
        <SummaryCard label="Faltando XML" tone="warn" value={payload?.faltandoXmlCount ?? 0} />
        <SummaryCard label="Faltando comprovante" tone="warn" value={payload?.faltandoComprovanteCount ?? 0} />
        <SummaryCard label="Prontos p/ chamado" tone="ok" value={payload?.prontosChamadoCount ?? 0} />
        <SummaryCard label="Visíveis" value={rows.length} />
      </div>

      <div className="pendentes-plan-toolbar">
        <label className="pendentes-plan-search">
          <Search size={16} aria-hidden="true" />
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar CTE, filial, série, documento..."
            value={query}
          />
        </label>
        <span>{formatGeneratedAt(payload?.generatedAt)}</span>
      </div>

      {error ? <div className="pendentes-plan-error">{error}</div> : null}
      {!error && !loading && (payload?.total ?? 0) === 0 ? (
        <div className="pendentes-plan-empty">
          Nenhum plano encontrado ainda. Rode "Consultar" (não executa nada, só atualiza a lista) e volte aqui.
        </div>
      ) : null}

      <div className="pendentes-plan-table-wrap">
        <table className="pendentes-plan-table">
          <thead>
            <tr>
              <th>CTE</th>
              <th>Filial</th>
              <th>Série</th>
              <th>Documento</th>
              <th>PDF</th>
              <th>XML</th>
              <th>Comprovante</th>
              <th>Chamado</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8}>Carregando...</td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={8}>Nenhum CTE encontrado.</td>
              </tr>
            ) : (
              rows.map((row) => <PlanTableRow key={row.cte} row={row} />)
            )}
          </tbody>
        </table>
      </div>

      <div className="pendentes-plan-source">{payload?.sourceFile || "Fonte não encontrada."}</div>
    </section>
  );
}

function PlanTableRow({ row }: { row: PendentesPlanRow }) {
  return (
    <tr>
      <td>
        <strong>{row.cte || "-"}</strong>
      </td>
      <td>{row.filial || "-"}</td>
      <td>{row.serie || "-"}</td>
      <td>{row.documento || "-"}</td>
      <td>
        <StatusChip label={row.faltaPdf ? "Falta" : "OK"} ok={!row.faltaPdf} />
      </td>
      <td>
        <StatusChip label={row.faltaXml ? "Falta" : "OK"} ok={!row.faltaXml} />
      </td>
      <td>
        <ComprovanteChip row={row} />
      </td>
      <td>
        <StatusChip label={row.prontoChamado ? "Pronto" : "Aguardando"} ok={row.prontoChamado} />
      </td>
    </tr>
  );
}

function StatusChip({ label, ok }: { label: string; ok: boolean }) {
  return <span className={ok ? "pendentes-status-chip ok" : "pendentes-status-chip warn"}>{label}</span>;
}

function ComprovanteChip({ row }: { row: PendentesPlanRow }) {
  if (row.comprovanteStatus === "nao_exige") {
    return (
      <span className="pendentes-status-chip neutral" title="CTE sem NMGNRE — não exige guia/comprovante.">
        Não exige
      </span>
    );
  }
  if (row.comprovanteStatus === "ok") {
    return <span className="pendentes-status-chip ok">OK ({row.comprovanteCount})</span>;
  }
  const missing = [!row.hasGuia && "guia", !row.hasComprovanteFile && "comprovante"].filter(Boolean).join(" + ");
  return (
    <span className="pendentes-status-chip warn" title={`Falta: ${missing}`}>
      Falta ({missing})
    </span>
  );
}

function SummaryCard({ label, value, tone = "" }: { label: string; value: number; tone?: string }) {
  return (
    <article className={`pendentes-plan-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function formatGeneratedAt(value?: string | null) {
  if (!value) return "Sem atualização registrada.";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return `Atualizado em ${parsed.toLocaleString("pt-BR")}`;
}
