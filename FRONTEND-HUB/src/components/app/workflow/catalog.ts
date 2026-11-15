import {
  Database,
  FileSpreadsheet,
  GitCompareArrows,
  FolderCheck,
  FileText,
  FileCode2,
  Paperclip,
  Ticket,
  FileOutput,
  ExternalLink,
  PanelTop,
  RefreshCw,
} from "lucide-react";
import type { WorkflowKind } from "@/services/scheduled-workflow";

export const workflowCatalog = {
  tariffs: { label: "Atualizar tarifário", icon: RefreshCw, group: "Novelis" },
  novelis_report: { label: "Relatório Novelis", icon: FileSpreadsheet, group: "Consulta" },
  sql: { label: "Consultar SQL", icon: Database, group: "Consulta" },
  compare: { label: "Comparar relatório", icon: GitCompareArrows, group: "Conferência" },
  files: { label: "Verificar arquivos", icon: FolderCheck, group: "Conferência" },
  pdf: { label: "Baixar PDF", icon: FileText, group: "Documentos" },
  xml: { label: "Baixar XML", icon: FileCode2, group: "Documentos" },
  proof: { label: "Buscar comprovante", icon: Paperclip, group: "Documentos" },
  tickets: { label: "Abrir chamado", icon: Ticket, group: "Novelis" },
  generate_report: { label: "Gerar relatório", icon: FileOutput, group: "Finalização" },
  open_report: { label: "Abrir relatório final", icon: ExternalLink, group: "Finalização" },
  completion_modal: { label: "Modal de finalização", icon: PanelTop, group: "Finalização" },
} satisfies Record<WorkflowKind, { label: string; icon: typeof Database; group: string }>;
