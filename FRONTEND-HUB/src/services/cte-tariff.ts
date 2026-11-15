export interface CteTariffReference {
  id: string;
  idTarifa: string;
  idRota: string;
  origem: string;
  destino: string;
  tarifaTon: string | null;
  valorTotal: string | null;
  capacidadeTon: string | null;
  veiculo: string;
  operacao: string;
  faturamento: string;
  inicio: string | null;
  fim: string | null;
}
export interface CteTariffAudit {
  status:
    "conferido" | "divergente" | "ambiguo" | "sem_tarifa" | "dados_incompletos" | "indisponivel";
  origem: string;
  destino: string;
  dataReferencia: string | null;
  idObservacao: string | null;
  percursoObservacao: string | null;
  tonObservacao: string | null;
  freteSql: string | null;
  outrosSql: string | null;
  frevalSql: string | null;
  totalSql: string | null;
  totalReferencia: string | null;
  selecionada: CteTariffReference | null;
  tonConfere: boolean | null;
  freteConfere: boolean | null;
  composicaoConfere: boolean | null;
  diferencaFrete: string | null;
  diferencaTotal: string | null;
  alertas: string[];
  criterio?: string;
  candidatos: CteTariffReference[];
  totalCandidatos: number;
  catalogoAtualizadoEm: string | null;
  catalogoStatus: string | null;
}
export const cteTariffLabels: Record<CteTariffAudit["status"], string> = {
  conferido: "Conferido",
  divergente: "Divergência",
  ambiguo: "Conferir tarifa",
  sem_tarifa: "Sem tarifa",
  dados_incompletos: "Dados incompletos",
  indisponivel: "Indisponível",
};
