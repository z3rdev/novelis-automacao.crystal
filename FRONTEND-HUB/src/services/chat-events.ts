import type { ChatMessage } from "./chat";

export type ChatLiveEvent =
  | { type: "connected" | "disconnected" | "chat.changed" }
  | { type: "message.created"; room_id: string; message: ChatMessage };

export function watchChatEvents(
  baseUrl: string,
  session: () => string | null,
  receive: (event: ChatLiveEvent) => void,
) {
  let stopped = false;
  let socket: WebSocket | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let delay = 1000;
  const connect = () => {
    const token = session();
    if (stopped || !token) return;
    const url = new URL(baseUrl.replace(/\/$/, "") + "/chat/live", window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(url);
    socket.onopen = () => socket?.send(JSON.stringify({ session: token }));
    socket.onmessage = (message) => {
      let event: { type?: string; room_id?: string; message?: ChatMessage };
      try {
        event = JSON.parse(String(message.data));
      } catch {
        return;
      }
      if (!event || typeof event !== "object") return;
      if (
        event.type === "message.created" &&
        typeof event.room_id === "string" &&
        event.message?.id
      ) {
        receive({ type: "message.created", room_id: event.room_id, message: event.message });
        return;
      }
      if (event.type === "local") {
        stopped = true;
        return;
      }
      if (event.type === "ping") {
        socket?.send(JSON.stringify({ type: "pong" }));
        return;
      }
      if (event.type === "chat.changed") {
        delay = 1000;
        receive({ type: "connected" });
        receive({ type: "chat.changed" });
      }
    };
    socket.onclose = () => {
      receive({ type: "disconnected" });
      if (!stopped) {
        timer = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      }
    };
    socket.onerror = () => socket?.close();
  };
  connect();
  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    socket?.close();
  };
}
