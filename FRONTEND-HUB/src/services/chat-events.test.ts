import { afterEach, expect, it, vi } from "vitest";
import { watchChatEvents } from "./chat-events";

class Socket {
  static instances: Socket[] = [];
  onopen?: () => void;
  onmessage?: (event: { data: string }) => void;
  onclose?: () => void;
  onerror?: () => void;
  send = vi.fn();
  close = vi.fn(() => this.onclose?.());
  constructor(public url: URL) {
    Socket.instances.push(this);
  }
}
afterEach(() => {
  Socket.instances = [];
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("autentica no primeiro frame, recebe mudanças e reconecta sem pôr sessão na URL", () => {
  vi.useFakeTimers();
  vi.stubGlobal("WebSocket", Socket);
  const receive = vi.fn();
  const stop = watchChatEvents("http://127.0.0.1:18036/api/hub", () => "session-fixture", receive);
  const first = Socket.instances[0]!;
  expect(String(first.url)).toBe("ws://127.0.0.1:18036/api/hub/chat/live");
  first.onopen?.();
  expect(first.send).toHaveBeenCalledWith(JSON.stringify({ session: "session-fixture" }));
  first.onmessage?.({ data: JSON.stringify({ type: "chat.changed" }) });
  expect(receive).toHaveBeenCalledWith({ type: "chat.changed" });
  const delivery = { type: "message.created", room_id: "room", message: { id: "message" } };
  first.onmessage?.({ data: JSON.stringify(delivery) });
  expect(receive).toHaveBeenCalledWith(delivery);
  first.onmessage?.({ data: JSON.stringify({ type: "ping" }) });
  expect(first.send).toHaveBeenCalledWith(JSON.stringify({ type: "pong" }));
  first.onclose?.();
  vi.advanceTimersByTime(1000);
  expect(Socket.instances).toHaveLength(2);
  stop();
  vi.advanceTimersByTime(60000);
  expect(Socket.instances).toHaveLength(2);
});

it("encerra a conexão quando o backend informa o modo local", () => {
  vi.useFakeTimers();
  vi.stubGlobal("WebSocket", Socket);
  const stop = watchChatEvents("http://localhost:8000/api/hub", () => "session", vi.fn());
  const first = Socket.instances[0]!;
  first.onmessage?.({ data: JSON.stringify({ type: "local" }) });
  first.onclose?.();
  vi.advanceTimersByTime(60000);
  expect(Socket.instances).toHaveLength(1);
  stop();
});
