export type DocStatus = "disponivel" | "faltando" | "nao_exige";
export type RunState = "aguardando" | "executando" | "parando" | "concluida" | "falhou" | "cancelada";
export type StageId = "consulta" | "pdf" | "xml" | "comprovantes" | "chamados";
export type StageState = "aguardando" | "executando" | "parando" | "cancelada" | "concluida" | "falhou" | "ignorada";
export type Severity = "info" | "sucesso" | "aviso" | "erro" | "debug";
export type FlowId = "completo" | "documentos" | "somente_pdf" | "somente_xml" | "somente_chamados" | "consulta";

export interface Cte {
  id: string; // filial-série-número
  filial: number;
  serie: number;
  numero: number;
  chave: string;
  emissao: string; // ISO
  valor: number | null;
  remetente: string;
  destinatario: string;
  origem: string;
  destino: string;
  pdf: DocStatus;
  xml: DocStatus;
  comprovante: DocStatus;
  prontoChamado: boolean;
  historico: { data: string; evento: string }[];
}

export interface Overview {
  naFila: number;
  pdfFaltando: number;
  xmlFaltando: number;
  comprovanteFaltando: number;
  prontosChamado: number;
  ultimaAtualizacao: string;
  execucao: RunStatus;
}

export interface StageProgress { id: StageId; state: StageState; done: number; total: number; atual?: string; detalhe?: string; reaproveitados?: number }

export interface RunStatus {
  id: string | null;
  flow: FlowId | null;
  state: RunState;
  etapaAtual: StageId | null;
  cteAtual: string | null;
  processados: number;
  total: number;
  iniciadoEm: string | null;
  stages: StageProgress[];
}

export interface StartRunRequest { flow: FlowId; ctes?: string[]; periodoDias?: number }

export interface LogEntry { id: string; time: string; severity: Severity; source: string; message: string; details?: string | undefined }

export interface DacteJob { id?: string; pdfUrl?: string; cte: string; metodo: "crystal" | "xml"; state: StageState; etapa: string; erro?: string | undefined; arquivo?: string | undefined; qrCode?: "ok" | "falha" | "pendente"; codigoBarras?: "ok" | "falha" | "pendente"; geradoEm?: string }

export interface Chamado {
  cte: string; data: string; valorTotal: number | null; aberturaNovelis: string | null; idTarifario: string;
  chamado: string | null; jda: string | null; andamento: "na_fila" | "aberto" | "em_analise" | "solucionado" | "falhou";
  responsavel: string; origem: string; destino: string;
}

export interface HealthItem { id: string; grupo: string; nome: string; status: "ok" | "aviso" | "erro"; detalhe: string; latenciaMs?: number }

export interface ConfigField { key: string; label: string; value: string; sensitive?: boolean; hint?: string; readOnly?: boolean }
export interface ConfigGroup { id: "banco" | "documentos" | "automacoes" | "caminhos"; titulo: string; fields: ConfigField[] }

export interface AutomationStep { id: string; ordem: number; nome: string; acao: string; seletor: string; aba: string; timeoutMs: number; captura: boolean; ativo: boolean }

export interface BrowserFrame { url: string; titulo: string; acao: string; screenshot?: string; ativo: boolean }

export interface AutomationApi {
  ping(): Promise<{ ok: boolean; versao: string; latenciaMs: number }>;
  getOverview(): Promise<Overview>;
  listCtes(): Promise<Cte[]>;
  refreshCtes(periodoDias: number): Promise<{ atualizados: number; state?: string }>;
  getRun(): Promise<RunStatus>;
  startRun(req: StartRunRequest): Promise<RunStatus>;
  stopRun(): Promise<RunStatus>;
  listDacteJobs(): Promise<DacteJob[]>;
  generateDacte(ctes: string[], metodo: "crystal" | "xml"): Promise<void>;
  listChamados(): Promise<Chamado[]>;
  listLogs(since?: string): Promise<LogEntry[]>;
  getBrowserFrame(): Promise<BrowserFrame>;
  focusBrowser(): Promise<void>;
  getHealth(): Promise<HealthItem[]>;
  getConfig(): Promise<ConfigGroup[]>;
  saveConfig(groups: ConfigGroup[]): Promise<void>;
  listSteps(): Promise<AutomationStep[]>;
  saveSteps(steps: AutomationStep[]): Promise<void>;
}
