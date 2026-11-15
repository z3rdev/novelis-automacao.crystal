import type { ChatDetail, ChatMessage } from "./chat";

export function mergeChatMessage(detail: ChatDetail, message: ChatMessage): ChatDetail {
  const matches = (value: ChatMessage) =>
    value.id === message.id || Boolean(message.client_id && value.client_id === message.client_id);
  const existing = detail.messages.find(matches);
  if (message.delivery && existing && !existing.delivery) return detail;
  const messages = [...detail.messages.filter((value) => !matches(value)), message];
  messages.sort(
    (left, right) =>
      Number(Boolean(left.delivery)) - Number(Boolean(right.delivery)) || left.seq - right.seq,
  );
  return { ...detail, messages };
}

export function mergeChatSnapshot(
  snapshot: ChatDetail,
  cached: ChatDetail | undefined,
): ChatDetail {
  const latest = snapshot.messages.at(-1)?.seq ?? 0;
  return (cached?.messages ?? [])
    .filter((message) => message.delivery || message.seq > latest)
    .reduce(mergeChatMessage, snapshot);
}
