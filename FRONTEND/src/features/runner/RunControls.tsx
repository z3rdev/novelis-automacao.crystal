import { FileSpreadsheet, ListOrdered, Play, RefreshCw, Square, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { getPendentesPlan, type AutomationEvent, type FlowDefinition, type PendentesPlanRow, type RunSnapshot, type RunStartPayload } from "../../lib/api";
import "./runner.css";
import { useRodoparEnabled } from "../steps/useRodoparEnabled";

const CUSTOM_CTE_OPTION = "__custom__";

function cteStatusLabel(row: PendentesPlanRow): string {
  if (row.prontoChamado) return "pronto p/ chamado";
  if (row.faltaPdf) return "falta PDF";
  if (row.faltaXml) return "falta XML";
  if (row.faltaComprovante) return "falta comprovante";
  return "pendente";
}

interface Props {
  run: RunSnapshot | null;
  flows: FlowDefinition[];
  events: AutomationEvent[];
  onRefresh: () => Promise<void>;
  onStart: (payload: RunStartPayload) => Promise<void>;
  onStop: () => Promise<void>;
}

const PROGRESS_LABELS: Record<string, string> = {
  "crystal_pdf.progress": "Gerando PDFs pelo banco / Crystal",
  "rodopar_pdf.progress": "Baixando PDFs Rodopar",
  "comprovante_local.progress": "Buscando comprovantes",
  "chamado_novelis.progress": "Abrindo chamados Novelis",
};

export function RunControls({ run, flows, events, onRefresh, onStart, onStop }: Props) {
  const rodoparEnabled = useRodoparEnabled();
  const [flow, setFlow] = useState("pendentes");
  const [testMode, setTestMode] = useState(false);
  const [filial, setFilial] = useState("");
  const [serie, setSerie] = useState("10");
  const [documento, setDocumento] = useState("");
  const [cte, setCte] = useState("");
  const [customCte, setCustomCte] = useState("");
  const [ctePlanRows, setCtePlanRows] = useState<PendentesPlanRow[]>([]);
  const [ctePlanLoading, setCtePlanLoading] = useState(false);
  const [ctePlanError, setCtePlanError] = useState("");
  const [rodoparOverlayEnabled, setRodoparOverlayEnabled] = useState(true);
  const [manualEnabled, setManualEnabled] = useState(false);
  const [manualSequence, setManualSequence] = useState("");
  const [manualSpreadsheet, setManualSpreadsheet] = useState<File | null>(null);
  const [manualError, setManualError] = useState("");
  const [daysModalOpen, setDaysModalOpen] = useState(false);
  const [daysBack, setDaysBack] = useState(5);
  const [skipChamadoMissingComprovante, setSkipChamadoMissingComprovante] = useState(true);
  const manualFileInputRef = useRef<HTMLInputElement | null>(null);
  const running = run?.status === "running" || run?.status === "stopping";
  const rodoparPdf = flow === "pdf-rodopar" || flow === "rodopar-pdf";
  const rodoparOverlayAvailable = rodoparPdf && rodoparEnabled;
  const manualSourceAvailable = flow === "pendentes" || flow === "consulta-pendentes" || flow === "consulta";
  const sqlDaysAvailable = flow === "pendentes" || flow === "consulta-pendentes" || flow === "consulta";

  const progress = useMemo(() => {
    if (!running || !run?.id) return null;
    const latest = events.find(
      (event) => event.run_id === run.id && event.kind in PROGRESS_LABELS,
    );
    if (!latest) return null;
    const current = Number(latest.payload?.current ?? 0);
    const total = Number(latest.payload?.total ?? 0);
    if (!total) return null;
    return { current, total, label: PROGRESS_LABELS[latest.kind], detail: latest.message };
  }, [events, running, run?.id]);

  useEffect(() => {
    if (!flows.length) return;
    if (!flows.some((item) => item.key === flow && item.enabled !== false)) setFlow(flows.find((item) => item.enabled !== false)?.key || "pendentes");
  }, [flow, flows]);

  useEffect(() => {
    if (!manualSourceAvailable) {
      setManualEnabled(false);
      setManualError("");
    }
  }, [manualSourceAvailable]);

  useEffect(() => {
    if (!testMode || rodoparPdf) return;
    void loadCtePlan();
  }, [testMode, rodoparPdf]);

  async function loadCtePlan() {
    setCtePlanLoading(true);
    setCtePlanError("");
    try {
      const plan = await getPendentesPlan();
      setCtePlanRows(plan.rows);
    } catch (err) {
      setCtePlanError(err instanceof Error ? err.message : "Falha ao carregar lista de CTEs.");
    } finally {
      setCtePlanLoading(false);
    }
  }

  function handleStartClick() {
    // Manual entry looks up each CTE individually by its own chave (see
    // ManualInputResolver.apply, which forces refreshSql=False whenever it
    // resolves rows) -- the "last N days" bulk SQL query never runs for it,
    // so asking for a day range here would just be a prompt about a setting
    // that gets silently ignored.
    const usingManualEntry = manualSourceAvailable && manualEnabled;
    if (sqlDaysAvailable && !usingManualEntry) {
      setDaysModalOpen(true);
      return;
    }
    void submit();
  }

  async function submit(days?: number) {
    setManualError("");
    const manualPayload = await buildManualPayload();
    if (manualPayload === false) return;
    setDaysModalOpen(false);
    const effectiveCte = cte === CUSTOM_CTE_OPTION ? customCte.trim() : cte;
    await onStart({
      flow,
      dry_run: false,
      sample_filial: testMode && rodoparPdf ? filial : "",
      sample_serie: testMode && rodoparPdf ? serie : "",
      sample_documento: testMode && rodoparPdf ? documento : "",
      sample_cte: testMode && !rodoparPdf ? effectiveCte : "",
      rodopar_replay_overlay_enabled: rodoparOverlayAvailable ? rodoparOverlayEnabled : undefined,
      pendentes_sql_days_back: sqlDaysAvailable ? (days ?? daysBack) : undefined,
      pendentes_skip_chamado_missing_comprovante: sqlDaysAvailable ? skipChamadoMissingComprovante : undefined,
      ...manualPayload,
    });
  }

  async function buildManualPayload(): Promise<Partial<RunStartPayload> | false> {
    if (!manualSourceAvailable || !manualEnabled) return {};
    if (!manualSequence.trim() && !manualSpreadsheet) {
      setManualError("Informe uma sequência ou selecione uma planilha.");
      return false;
    }
    try {
      return {
        manual_ctes: manualSequence.trim(),
        manual_spreadsheet: manualSpreadsheet ? await fileToManualSpreadsheet(manualSpreadsheet) : null,
      };
    } catch (err) {
      setManualError(err instanceof Error ? err.message : "Falha ao ler a planilha.");
      return false;
    }
  }

  function clearManualSpreadsheet() {
    setManualSpreadsheet(null);
    if (manualFileInputRef.current) manualFileInputRef.current.value = "";
  }

  return (
    <section className="panel run-panel">
      <div className="panel-title">
        <Play size={18} aria-hidden="true" />
        <h2>Execução</h2>
        <span className={`pill status-${run?.status ?? "idle"}`}>
          {run?.status ?? "idle"}
        </span>
      </div>

      {progress ? (
        <div className="run-progress">
          <div className="run-progress-label">
            <span>{progress.label}</span>
            <span>
              {progress.current}/{progress.total}
            </span>
          </div>
          <progress className="run-progress-bar" max={progress.total} value={progress.current} />
          <p className="run-progress-detail">{progress.detail}</p>
        </div>
      ) : null}

      <div className="run-grid">
        <label className="field wide flow-field">
          <span>Fluxo</span>
          <select value={flow} onChange={(event) => setFlow(event.target.value)}>
            {flows.map((item) => (
              <option disabled={item.enabled === false} key={item.key} value={item.key}>
                {item.name}{item.enabled === false ? " (desabilitado)" : ""}
              </option>
            ))}
          </select>
        </label>
        {testMode && rodoparPdf ? (
          <div className="run-triplet wide">
            <label className="field">
              <span>Filial teste</span>
              <input
                placeholder="ex: 2"
                value={filial}
                onChange={(event) => setFilial(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Série teste</span>
              <input
                placeholder="ex: 10"
                value={serie}
                onChange={(event) => setSerie(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Documento teste</span>
              <input
                placeholder="ex: 16506"
                value={documento}
                onChange={(event) => setDocumento(event.target.value)}
              />
            </label>
          </div>
        ) : null}
        {testMode && !rodoparPdf ? (
          <div className="field wide">
            <span>CTE teste</span>
            <div className="run-cte-select-row">
              <select value={cte} onChange={(event) => setCte(event.target.value)}>
                <option value="">
                  {ctePlanLoading ? "Carregando CTEs..." : "Selecione um CTE..."}
                </option>
                {ctePlanRows.map((row) => (
                  <option key={row.cte} value={row.cte}>
                    {row.cte} — {cteStatusLabel(row)}
                  </option>
                ))}
                <option value={CUSTOM_CTE_OPTION}>Outro (digitar manualmente)</option>
              </select>
              <button
                className="icon-button"
                disabled={ctePlanLoading}
                onClick={() => void loadCtePlan()}
                title="Recarregar lista de CTEs"
                type="button"
              >
                <RefreshCw size={16} aria-hidden="true" />
              </button>
            </div>
            {cte === CUSTOM_CTE_OPTION ? (
              <input
                placeholder="ex: 2-10-16506"
                value={customCte}
                onChange={(event) => setCustomCte(event.target.value)}
              />
            ) : null}
            {ctePlanError ? <p className="run-message error-text">{ctePlanError}</p> : null}
          </div>
        ) : null}
        {manualSourceAvailable ? (
          <div className="run-manual-panel wide">
            <label className="run-option checkbox-field">
              <input
                type="checkbox"
                checked={manualEnabled}
                onChange={(event) => setManualEnabled(event.target.checked)}
              />
              <span>Entrada manual</span>
            </label>

            {manualEnabled ? (
              <>
                <label className="run-option checkbox-field manual-chamado-option">
                  <input
                    type="checkbox"
                    checked={!skipChamadoMissingComprovante}
                    onChange={(event) => setSkipChamadoMissingComprovante(!event.target.checked)}
                  />
                  <span>Abrir chamado mesmo sem guia ou comprovante</span>
                </label>
                <div className="run-manual-grid">
                  <label className="field">
                    <span>
                      <FileSpreadsheet size={14} aria-hidden="true" />
                      Planilha
                    </span>
                    <input
                      accept=".xlsx,.xlsm,.csv"
                      className="manual-file-input"
                      id="manual-spreadsheet-file"
                      onChange={(event) => setManualSpreadsheet(event.target.files?.[0] ?? null)}
                      ref={manualFileInputRef}
                      type="file"
                    />
                    <div className="manual-file-picker">
                      <label className="secondary-button manual-file-button" htmlFor="manual-spreadsheet-file">
                        <FileSpreadsheet size={16} aria-hidden="true" />
                        Selecionar
                      </label>
                      <span className="manual-file-name" title={manualSpreadsheet?.name || ""}>
                        {manualSpreadsheet?.name || "Sem arquivo"}
                      </span>
                      {manualSpreadsheet ? (
                        <button className="icon-button" onClick={clearManualSpreadsheet} title="Limpar planilha" type="button">
                          <X size={16} aria-hidden="true" />
                        </button>
                      ) : null}
                    </div>
                  </label>
                  <label className="field">
                    <span>
                      <ListOrdered size={14} aria-hidden="true" />
                      Sequência
                    </span>
                    <textarea
                      onChange={(event) => setManualSequence(event.target.value)}
                      placeholder="2-10-10402"
                      rows={4}
                      value={manualSequence}
                    />
                  </label>
                </div>
              </>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="button-row">
        <button className="primary-button" disabled={running} onClick={handleStartClick} type="button">
          <Play size={16} aria-hidden="true" />
          Iniciar
        </button>
        <button className="danger-button" disabled={!running} onClick={onStop} type="button">
          <Square size={16} aria-hidden="true" />
          Parar
        </button>
        <button className="icon-button" onClick={onRefresh} title="Atualizar" type="button">
          <RefreshCw size={16} aria-hidden="true" />
        </button>
      </div>

      <label className="run-option checkbox-field">
        <input
          type="checkbox"
          checked={testMode}
          onChange={(event) => setTestMode(event.target.checked)}
        />
        <span>Modo teste / campos manuais</span>
      </label>

      {rodoparOverlayAvailable ? (
        <label className="run-option checkbox-field">
          <input
            type="checkbox"
            checked={rodoparOverlayEnabled}
            onChange={(event) => setRodoparOverlayEnabled(event.target.checked)}
          />
          <span>Overlay Rodopar</span>
        </label>
      ) : null}

      {manualError ? <p className="run-message error-text">{manualError}</p> : null}
      <p className="run-message">{run?.message ?? "Aguardando backend."}</p>

      {daysModalOpen ? (
        <div
          aria-labelledby="run-days-modal-title"
          aria-modal="true"
          className="run-days-modal-backdrop"
          onClick={() => setDaysModalOpen(false)}
          role="dialog"
        >
          <div className="run-days-modal" onClick={(event) => event.stopPropagation()}>
            <strong id="run-days-modal-title">Consultar quantos dias?</strong>
            <p>Período consultado no SQL pra montar a lista de pendentes.</p>
            <div className="run-days-modal-options">
              {[5, 10, 20].map((option) => (
                <button
                  className={`run-days-option${daysBack === option ? " selected" : ""}`}
                  key={option}
                  onClick={() => setDaysBack(option)}
                  type="button"
                >
                  {option} dias
                </button>
              ))}
            </div>
            <label className="run-option checkbox-field">
              <input
                checked={skipChamadoMissingComprovante}
                onChange={(event) => setSkipChamadoMissingComprovante(event.target.checked)}
                type="checkbox"
              />
              <span>Pular abertura de chamado Novelis dos CTEs com guia/comprovante faltando</span>
            </label>
            <div className="run-days-modal-actions">
              <button className="secondary-button" onClick={() => setDaysModalOpen(false)} type="button">
                Cancelar
              </button>
              <button className="primary-button" onClick={() => void submit(daysBack)} type="button">
                <Play size={16} aria-hidden="true" />
                Iniciar
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

async function fileToManualSpreadsheet(file: File) {
  const dataUrl = await readFileAsDataUrl(file);
  return {
    filename: file.name,
    content_base64: dataUrl.split(",", 2)[1] ?? dataUrl,
  };
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Falha ao ler a planilha selecionada."));
    reader.onload = () => resolve(String(reader.result || ""));
    reader.readAsDataURL(file);
  });
}
