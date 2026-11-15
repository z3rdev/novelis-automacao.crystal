export interface ChatActor {
  key: string;
  name: string;
  sector: string | null;
}
export interface ChatRoom {
  id: string;
  title: string;
  target_type: "operator" | "sector";
  target: string;
  creator: string;
  unread: number;
  last_message: string | null;
  last_message_at: string | null;
}
export interface ChatInbox {
  rooms: ChatRoom[];
  unread: number;
  actor: ChatActor;
  latest_unread_seq?: number;
  latest_room?: string;
}
export interface ChatDirectory {
  operators: (ChatActor & { windows_user: string; online: boolean })[];
  sectors: { code: string; name: string }[];
}
export interface ChatMessage {
  id: string;
  seq: number;
  sender: string;
  sender_name: string;
  body: string;
  kind: "text" | "request" | "attachment";
  request_id: string | null;
  created_at: string;
}
export type GnreFileKind = "guia" | "comprovante";
export interface GnreFile {
  id: string;
  kind: GnreFileKind | "combined";
  sha256: string;
  original_name?: string;
  uploaded_name?: string;
  uploaded_at?: string;
}
export interface GnreRequest {
  id: string;
  cte: string;
  note: string;
  chamado: string;
  chamado_url: string | null;
  requested_by: string;
  requested_name: string;
  assigned_to: string | null;
  assigned_name: string | null;
  state:
    "waiting" | "in_progress" | "partial" | "publishing" | "available" | "archived" | "expired";
  expires_at?: string | null;
  guia: GnreFile | null;
  comprovante: GnreFile | null;
  combined: GnreFile | null;
  directory: string;
  created_at: string;
  updated_at: string;
}
export interface ChatDetail {
  messages: ChatMessage[];
  before: number | null;
  requests: GnreRequest[];
  delivery_warning?: string | null;
}
export interface ChatApi {
  getChatInbox(): Promise<ChatInbox>;
  getChatDirectory(): Promise<ChatDirectory>;
  createChatRoom(target_type: "operator" | "sector", target: string): Promise<{ id: string }>;
  getChatRoom(id: string, before?: number): Promise<ChatDetail>;
  sendChatMessage(id: string, body: string, client_id: string): Promise<ChatMessage>;
  readChatRoom(id: string, through: number): Promise<void>;
  requestGnre(
    id: string,
    body: { cte: string; note: string; chamado: string },
  ): Promise<{ id: string }>;
  claimGnre(room: string, id: string): Promise<void>;
  uploadGnre(
    room: string,
    id: string,
    kind: GnreFileKind,
    file: File,
    clientId: string,
  ): Promise<ChatDetail>;
  downloadGnre(room: string, id: string, kind: GnreFileKind | "combined"): Promise<Blob>;
}
export const chatStates = {
  waiting: "Aguardando atendimento",
  in_progress: "Em atendimento",
  partial: "Documentação parcial",
  publishing: "Entregando documentos",
  available: "Documentação disponível",
  archived: "Disponível no MinIO",
  expired: "Prazo de armazenamento encerrado",
};
