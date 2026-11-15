import { expect, it } from "vitest";
import type { ChatDetail, ChatMessage } from "./chat";
import { mergeChatMessage, mergeChatSnapshot } from "./chat-cache";

const message: ChatMessage = {
  id: "confirmed",
  seq: 20,
  client_id: "attempt",
  sender: "operator",
  sender_name: "Operador",
  body: "Guia enviada",
  kind: "text",
  request_id: null,
  created_at: "2026-11-15T19:00:00Z",
};
const empty: ChatDetail = { messages: [], requests: [], before: null };

it("reconcilia a mensagem provisória com WebSocket e confirmação HTTP", () => {
  const pending = mergeChatMessage(empty, { ...message, id: "pending", delivery: "sending" });
  const confirmed = mergeChatMessage(pending, message);
  expect(mergeChatMessage(confirmed, message).messages).toEqual([message]);
  expect(mergeChatSnapshot(empty, confirmed).messages).toEqual([message]);
});

it("preserva tentativas pendentes durante a atualização e aceita a confirmação", () => {
  const pending = { ...message, id: "pending", delivery: "sending" as const };
  const cached = mergeChatMessage(empty, pending);
  expect(mergeChatSnapshot(empty, cached).messages).toEqual([pending]);
  expect(mergeChatSnapshot({ ...empty, messages: [message] }, cached).messages).toEqual([message]);
});
