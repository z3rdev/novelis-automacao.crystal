import type {
  AutomationApi, AutomationStep, Chamado, ConfigGroup, Cte, DacteJob, DocStatus, LogEntry,
  RunStatus, Severity, StageId, StageProgress, StartRunRequest,
} from "./types";

// PRNG determinístico para dados estáveis entre recargas.
let seed = 42;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const pick = <T,>(a: readonly T[]): T => a[Math.floor(rnd() * a.length)] as T;
const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms));

const cidades = ["Pindamonhangaba/SP", "Santo André/SP", "Itu/SP", "Ouro Preto/MG", "Camaçari/BA", "Recife/PE", "Curitiba/PR", "Betim/MG", "Manaus/AM", "Jundiaí/SP"];
const clientes = ["Novelis do Brasil Ltda", "Ambev S.A.", "Crown Embalagens", "Ball Embalagens", "Arconic Indústria", "Tetra Pak Ltda"];
const resp = ["Ana Souza", "Carlos Lima", "Fernanda Rocha", "Marcos Pereira", "Juliana Alves"];

const now = Date.now();
const day = 86400000;
const ctes: Cte[] = Array.from({ length: 64 }, (_, i) => {
  const filial = pick([1, 2, 2, 3, 5]);
  const serie = pick([1, 10, 10, 20]);
  const numero = 10001 + i * 7 + Math.floor(rnd() * 5);
  const st = (): DocStatus => (rnd() < 0.62 ? "disponivel" : "faltando");
  const pdf = st(), xml = st();
  const comprovante: DocStatus = rnd() < 0.2 ? "nao_exige" : st();
  const emissao = new Date(now - Math.floor(rnd() * 30) * day - Math.floor(rnd() * day)).toISOString();
  const chave = "35" + "2611" + "12345678000190" + "57" + String(serie).padStart(3, "0") + String(numero).padStart(9, "0") + "1" + String(Math.floor(rnd() * 1e8)).padStart(8, "0") + "0";
  return {
    id: `${filial}-${serie}-${numero}`, filial, serie, numero, chave: chave.slice(0, 44).padEnd(44, "0"),
    emissao, valor: Math.round((800 + rnd() * 18000) * 100) / 100,
    remetente: "Novelis do Brasil Ltda", destinatario: pick(clientes),
    origem: pick(cidades.slice(0, 3)), destino: pick(cidades),
    pdf, xml, comprovante,
    prontoChamado: pdf === "disponivel" && xml === "disponivel" && comprovante !== "faltando",
    historico: [
      { data: emissao, evento: "CT-e emitido" },
      { data: new Date(new Date(emissao).getTime() + 3600000).toISOString(), evento: "Incluído na fila de pendências" },
    ],
  };
});

const recompute = (c: Cte) => { c.prontoChamado = c.pdf === "disponivel" && c.xml === "disponivel" && c.comprovante !== "faltando"; };

const chamados: Chamado[] = ctes.filter((c) => c.prontoChamado).map((c, i) => {
  const andamento = pick(["na_fila", "aberto", "em_analise", "solucionado", "solucionado", "falhou"] as const);
  const aberto = andamento !== "na_fila";
  return {
    cte: c.id, data: c.emissao, valorTotal: c.valor ?? 0,
    aberturaNovelis: aberto ? new Date(new Date(c.emissao).getTime() + 2 * day).toISOString() : null,
    idTarifario: `TAR-${String(3000 + i * 13).padStart(5, "0")}`,
    chamado: aberto && andamento !== "falhou" ? `INC${String(780000 + i * 31)}` : null,
    jda: andamento === "solucionado" ? `JDA-${String(55000 + i)}` : null,
    andamento, responsavel: pick(resp), origem: c.origem, destino: c.destino,
  };
});

let logs: LogEntry[] = [];
let logSeq = 0;
const log = (severity: Severity, source: string, message: string, details?: string) => {
  logs.push({ id: String(++logSeq), time: new Date().toISOString(), severity, source, message, details });
  if (logs.length > 800) logs = logs.slice(-800);
};
log("info", "sistema", "Serviço de automação iniciado", "uvicorn app.main:app --host 127.0.0.1 --port 8000");
log("sucesso", "sql", "Conexão com SQL Server estabelecida", "Driver ODBC 18 · banco RODOPAR_PROD");
log("aviso", "comprovantes", "Pasta de comprovantes lenta (1,8 s)", "\\\\srv-arquivos\\operacao\\comprovantes");

const jobs: DacteJob[] = ctes.filter((c) => c.pdf === "disponivel").slice(0, 12).map((c) => ({
  cte: c.id, metodo: "crystal", state: "concluida", etapa: "Arquivo salvo", arquivo: `C:\\Novelis\\DACTE\\${c.id}.pdf`,
  qrCode: rnd() < 0.9 ? "ok" : "falha", codigoBarras: "ok", geradoEm: c.emissao,
}));

const stageIds: StageId[] = ["consulta", "pdf", "xml", "comprovantes", "chamados"];
const blankStages = (): StageProgress[] => stageIds.map((id) => ({ id, state: "aguardando", done: 0, total: 0 }));
let run: RunStatus = { id: null, flow: null, state: "aguardando", etapaAtual: null, cteAtual: null, processados: 0, total: 0, iniciadoEm: null, stages: blankStages() };
let timer: ReturnType<typeof setInterval> | null = null;
let lastUpdate = new Date(now - 14 * 60000).toISOString();

  const flowStages: Record<string, StageId[]> = {
    consulta: ["consulta"],
  completo: stageIds, documentos: ["consulta", "pdf", "xml", "comprovantes"],
  somente_pdf: ["pdf"], somente_xml: ["xml"], somente_chamados: ["chamados"],
};

function tick() {
  const S = (id: StageId) => run.stages.find((s) => s.id === id)!;
  const active = run.stages.filter((s) => s.state === "executando");
  if (run.state === "parando") {
    active.forEach((s) => (s.state = "falhou"));
    run.state = "cancelada"; run.cteAtual = null;
    log("aviso", "execucao", "Execução cancelada pelo operador");
    stop(); return;
  }
  if (!active.length) {
    const next = run.stages.find((s) => s.state === "aguardando");
    if (!next) {
      run.state = "concluida"; run.etapaAtual = null; run.cteAtual = null;
      lastUpdate = new Date().toISOString();
      log("sucesso", "execucao", `Execução concluída: ${run.processados} CT-e(s) processados`);
      stop(); return;
    }
    next.state = "executando"; run.etapaAtual = next.id;
    log("info", next.id, `Etapa ${next.id.toUpperCase()} iniciada`, `${next.total} item(ns)`);
    // PDF e XML executam simultaneamente
    if (next.id === "pdf") { const x = S("xml"); if (x.state === "aguardando") { x.state = "executando"; log("info", "xml", "Etapa XML iniciada em paralelo ao PDF", "SEFAZ · consulta por chave"); } }
    return;
  }
  for (const s of active) {
    const pending = targets(s.id).filter((c) => !doneSet[s.id].has(c.id));
    if (s.id === "consulta") { s.done = s.total; s.state = "concluida"; log("sucesso", "consulta", `Consulta SQL retornou ${s.total} CT-e(s)`, "SELECT ... FROM CTE WHERE emissao >= @inicio"); continue; }
    const c = pending[0];
    if (!c) { s.state = "concluida"; log("sucesso", s.id, `Etapa ${s.id.toUpperCase()} concluída`); continue; }
    doneSet[s.id].add(c.id); s.done++; s.atual = c.id;
    if (s.id === "pdf") { run.cteAtual = c.id; c.pdf = "disponivel"; jobs.unshift({ cte: c.id, metodo: "crystal", state: "concluida", etapa: "Arquivo salvo", arquivo: `C:\\Novelis\\DACTE\\${c.id}.pdf`, qrCode: "ok", codigoBarras: "ok", geradoEm: new Date().toISOString() }); log("sucesso", "pdf", `DACTE ${c.id} gerado`, "Crystal Reports · DACTE_v4.rpt · 1,2 s"); }
    if (s.id === "xml") { if (rnd() < 0.12) log("erro", "xml", `SEFAZ não retornou XML para ${c.id}`, "HTTP 503 · cStat=108 Serviço paralisado momentaneamente"); else { c.xml = "disponivel"; log("sucesso", "xml", `XML ${c.id} baixado`, `chave ${c.chave}`); } }
    if (s.id === "comprovantes") { if (rnd() < 0.7) { c.comprovante = "disponivel"; log("info", "comprovantes", `Comprovante localizado para ${c.id}`, `\\\\srv-arquivos\\comprovantes\\${c.id}.pdf`); } else log("aviso", "comprovantes", `Comprovante não encontrado para ${c.id}`); }
    if (s.id === "chamados") { run.cteAtual = c.id; const ch = chamados.find((x) => x.cte === c.id); if (ch) { ch.andamento = "aberto"; ch.aberturaNovelis = new Date().toISOString(); ch.chamado = `INC${790000 + s.done}`; } log("sucesso", "chamados", `Chamado aberto no portal Novelis para ${c.id}`, "Playwright · chromium · aba Faturamento"); }
    recompute(c);
  }
  run.processados = run.stages.filter((s) => s.id !== "consulta").reduce((a, s) => a + s.done, 0);
}
const doneSet: Record<StageId, Set<string>> = { consulta: new Set(), pdf: new Set(), xml: new Set(), comprovantes: new Set(), chamados: new Set() };
let scope: Cte[] = ctes;
function targets(id: StageId): Cte[] {
  if (id === "pdf") return scope.filter((c) => c.pdf === "faltando" || doneSet.pdf.has(c.id));
  if (id === "xml") return scope.filter((c) => c.xml === "faltando" || doneSet.xml.has(c.id));
  if (id === "comprovantes") return scope.filter((c) => c.comprovante === "faltando" || doneSet.comprovantes.has(c.id));
  if (id === "chamados") return scope.filter((c) => (c.prontoChamado && chamados.find((x) => x.cte === c.id)?.andamento === "na_fila") || doneSet.chamados.has(c.id));
  return scope;
}
function stop() { if (timer) clearInterval(timer); timer = null; }

const steps: AutomationStep[] = [
  { id: "s1", ordem: 1, nome: "Abrir portal Novelis", acao: "navegar", seletor: "https://portal.novelis.com/login", aba: "principal", timeoutMs: 30000, captura: true, ativo: true },
  { id: "s2", ordem: 2, nome: "Autenticar usuário", acao: "preencher", seletor: "#username, #password", aba: "principal", timeoutMs: 15000, captura: false, ativo: true },
  { id: "s3", ordem: 3, nome: "Menu Faturamento", acao: "clicar", seletor: "nav >> text=Faturamento", aba: "principal", timeoutMs: 10000, captura: false, ativo: true },
  { id: "s4", ordem: 4, nome: "Novo chamado", acao: "clicar", seletor: "button:has-text('Novo chamado')", aba: "faturamento", timeoutMs: 10000, captura: true, ativo: true },
  { id: "s5", ordem: 5, nome: "Anexar DACTE e XML", acao: "upload", seletor: "input[type=file]", aba: "faturamento", timeoutMs: 45000, captura: true, ativo: true },
  { id: "s6", ordem: 6, nome: "Confirmar envio", acao: "clicar", seletor: "#btnEnviar", aba: "faturamento", timeoutMs: 20000, captura: true, ativo: true },
];

let config: ConfigGroup[] = [
  { id: "banco", titulo: "Banco de dados", fields: [
    { key: "db.host", label: "Servidor SQL", value: "srv-sql01.transp.local" },
    { key: "db.name", label: "Banco", value: "RODOPAR_PROD" },
    { key: "db.user", label: "Usuário", value: "svc_automacao" },
    { key: "db.password", label: "Senha", value: "S3nh@Forte!", sensitive: true },
  ] },
  { id: "documentos", titulo: "Documentos", fields: [
    { key: "dacte.report", label: "Relatório Crystal", value: "C:\\Novelis\\Relatorios\\DACTE_v4.rpt" },
    { key: "dacte.metodo", label: "Método padrão de geração", value: "crystal", hint: "crystal ou xml" },
    { key: "sefaz.cert", label: "Certificado A1", value: "C:\\Certificados\\transportadora.pfx" },
    { key: "sefaz.certPassword", label: "Senha do certificado", value: "certpass123", sensitive: true },
  ] },
  { id: "automacoes", titulo: "Automações", fields: [
    { key: "novelis.url", label: "URL do portal Novelis", value: "https://portal.novelis.com" },
    { key: "novelis.user", label: "Usuário do portal", value: "faturamento@transportadora.com.br" },
    { key: "novelis.password", label: "Senha do portal", value: "portal#2026", sensitive: true },
    { key: "playwright.headless", label: "Navegador oculto", value: "false", hint: "true ou false" },
  ] },
  { id: "caminhos", titulo: "Caminhos de arquivos", fields: [
    { key: "path.pdf", label: "Pasta DACTE (PDF)", value: "C:\\Novelis\\DACTE" },
    { key: "path.xml", label: "Pasta XML", value: "C:\\Novelis\\XML" },
    { key: "path.comprovantes", label: "Pasta de guias e comprovantes", value: "\\\\srv-arquivos\\operacao\\comprovantes" },
    { key: "path.planilhas", label: "Pasta de planilhas", value: "\\\\srv-arquivos\\operacao\\planilhas" },
  ] },
];

const clone = <T,>(v: T): T => structuredClone(v);

export const mockApi: AutomationApi = {
  async getSession() { return { identity: { windows_user: "Demonstração", computer_name: "Ambiente simulado", mac_addresses: [] }, session: null, pending_sync: 0 }; },
  async login() { throw new Error("A identificação Windows está disponível no backend local."); },
  async logout() {},
  async ping() { await delay(80); return { ok: true, versao: "demo-1.0", latenciaMs: 12 + Math.floor(Math.random() * 20) }; },
  async getOverview() {
    await delay(120);
    return {
      naFila: ctes.filter((c) => !c.prontoChamado).length + chamados.filter((c) => c.andamento === "na_fila").length,
      pdfFaltando: ctes.filter((c) => c.pdf === "faltando").length,
      xmlFaltando: ctes.filter((c) => c.xml === "faltando").length,
      comprovanteFaltando: ctes.filter((c) => c.comprovante === "faltando").length,
      prontosChamado: ctes.filter((c) => c.prontoChamado).length,
      ultimaAtualizacao: lastUpdate, execucao: clone(run),
    };
  },
  async listCtes() { await delay(150); return clone(ctes); },
  async refreshCtes(dias) { await delay(900); lastUpdate = new Date().toISOString(); log("info", "consulta", `Consulta manual dos últimos ${dias} dias`); return { atualizados: ctes.length }; },
  async getRun() { await delay(60); return clone(run); },
  async startRun(req: StartRunRequest) {
    await delay(200);
    if (run.state === "executando" || run.state === "parando") throw new Error("Já existe uma execução em andamento.");
    (Object.keys(doneSet) as StageId[]).forEach((k) => doneSet[k].clear());
    scope = req.ctes?.length ? ctes.filter((c) => req.ctes!.includes(c.id)) : ctes.filter((c) => Date.now() - new Date(c.emissao).getTime() <= (req.periodoDias ?? 30) * day);
    const active = flowStages[req.flow] ?? stageIds;
    run = { id: `RUN-${Date.now().toString().slice(-6)}`, flow: req.flow, state: "executando", etapaAtual: null, cteAtual: null, processados: 0, total: 0, iniciadoEm: new Date().toISOString(),
      stages: stageIds.map((id) => ({ id, state: active.includes(id) ? "aguardando" : "ignorada", done: 0, total: active.includes(id) ? targets(id).length : 0 })) };
    run.total = run.stages.filter((s) => s.id !== "consulta").reduce((a, s) => a + s.total, 0);
    log("info", "execucao", `Execução ${run.id} iniciada · fluxo ${req.flow}`, `${scope.length} CT-e(s) no escopo`);
    timer = setInterval(tick, 900);
    return clone(run);
  },
  async stopRun() { await delay(100); if (run.state === "executando") { run.state = "parando"; log("aviso", "execucao", "Solicitação de parada recebida"); } return clone(run); },
  async listDacteJobs() { await delay(100); return clone(jobs.slice(0, 60)); },
  async generateDacte(list, metodo) {
    await delay(300);
    list.forEach((id, i) => setTimeout(() => {
      const c = ctes.find((x) => x.id === id);
      const fail = metodo === "xml" && c?.xml !== "disponivel";
      jobs.unshift({ cte: id, metodo, state: fail ? "falhou" : "concluida", etapa: fail ? "XML arquivado não encontrado" : "Arquivo salvo", erro: fail ? "Arquivo XML ausente na pasta configurada" : undefined, arquivo: fail ? undefined : `C:\\Novelis\\DACTE\\${id}.pdf`, qrCode: fail ? "pendente" : "ok", codigoBarras: fail ? "pendente" : "ok", geradoEm: new Date().toISOString() });
      if (c && !fail) { c.pdf = "disponivel"; recompute(c); }
      log(fail ? "erro" : "sucesso", "pdf", fail ? `Falha ao gerar DACTE ${id} via XML` : `DACTE ${id} gerado via ${metodo === "xml" ? "XML arquivado" : "Crystal"}`);
    }, 700 * (i + 1)));
  },
  async listChamados() { await delay(120); return clone(chamados); },
  async listLogs(since) { await delay(50); return clone(since ? logs.filter((l) => Number(l.id) > Number(since)) : logs); },
    async focusBrowser() { await delay(50); },
    async getBrowserFrame() {
    await delay(50);
    const ativo = run.state === "executando" && run.etapaAtual === "chamados";
    return { ativo, url: ativo ? "https://portal.novelis.com/faturamento/chamados/novo" : "about:blank", titulo: ativo ? "Portal Novelis · Novo chamado" : "Navegador ocioso", acao: ativo ? `Preenchendo chamado do CT-e ${run.cteAtual}` : "Sem automação web ativa" };
  },
  async getHealth() {
    await delay(300);
    return [
      { id: "api", grupo: "Serviço", nome: "API FastAPI", status: "ok", detalhe: "Modo demonstração", latenciaMs: 14 },
      { id: "sql", grupo: "Banco de dados", nome: "SQL Server (ODBC 18)", status: "ok", detalhe: "srv-sql01 · 38 ms", latenciaMs: 38 },
      { id: "crystal", grupo: "Documentos", nome: "Crystal Reports Runtime", status: "ok", detalhe: "Versão 13.0.32" },
      { id: "cert", grupo: "Documentos", nome: "Certificado A1 SEFAZ", status: "aviso", detalhe: "Vence em 23 dias" },
      { id: "pw", grupo: "Automações", nome: "Playwright Chromium", status: "ok", detalhe: "chromium 128 instalado" },
      { id: "novelis", grupo: "Automações", nome: "Portal Novelis", status: "ok", detalhe: "HTTP 200 · 410 ms", latenciaMs: 410 },
      { id: "rede", grupo: "Caminhos", nome: "Pasta de comprovantes", status: "aviso", detalhe: "Resposta lenta (1,8 s)" },
      { id: "disk", grupo: "Caminhos", nome: "Disco C:\\", status: "ok", detalhe: "182 GB livres" },
    ];
  },
  async getConfig() { await delay(100); return clone(config); },
  async saveConfig(g) { await delay(300); config = clone(g); log("info", "config", "Configurações atualizadas"); },
  async listSteps() { await delay(100); return clone(steps); },
  async saveSteps(s) { await delay(300); steps.splice(0, steps.length, ...clone(s)); log("info", "automacao", "Passos da automação salvos"); },
};
