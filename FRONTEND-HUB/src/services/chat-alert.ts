export const chatAlertKey = "cargo-hub.chat-alert.v1";
export interface ChatAlert {
  unread: number;
  room: string;
  receivedAt: number;
}
export function readChatAlert(): ChatAlert | null {
  try {
    const value = JSON.parse(localStorage.getItem(chatAlertKey) ?? "null") as ChatAlert | null;
    return value && Number.isFinite(value.unread) && value.unread > 0 ? value : null;
  } catch {
    return null;
  }
}
