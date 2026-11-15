import type { ChatApi } from "./chat";

const connected = async (): Promise<never> => {
  throw new Error("Conecte ao backend para enviar mensagens e documentos.");
};
export const chatMock: ChatApi = {
  async getChatInbox() {
    return { rooms: [], unread: 0, actor: { key: "demo", name: "Operador", sector: "TI" } };
  },
  async getChatDirectory() {
    return { operators: [], sectors: [{ code: "FIN", name: "Financeiro" }] };
  },
  createChatRoom: connected,
  getChatRoom: connected,
  sendChatMessage: connected,
  readChatRoom: connected,
  requestGnre: connected,
  claimGnre: connected,
  uploadGnre: connected,
  downloadGnre: connected,
};
