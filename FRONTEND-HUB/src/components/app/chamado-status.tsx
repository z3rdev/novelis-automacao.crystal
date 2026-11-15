import { CheckCircle2, Clock, XCircle, Loader2 } from "lucide-react";
import type { Chamado } from "@/services";
import type { Tone } from "./status";
export const chamadoStates: Record<
  Chamado["andamento"],
  [Tone, string, React.ComponentType<{ className?: string }>]
> = {
  na_fila: ["warning", "Na fila", Clock],
  aberto: ["info", "Aberto", Loader2],
  em_analise: ["info", "Em análise", Loader2],
  solucionado: ["success", "Solucionado", CheckCircle2],
  falhou: ["error", "Falhou", XCircle],
};
