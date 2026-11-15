import type { Chamado } from "./types";
export interface ChamadoDetail extends Chamado {
  chave: string;
  statusOriginal: string;
  portalUrl: string | null;
  sincronizadoEm: string | null;
  descricao: string;
}
