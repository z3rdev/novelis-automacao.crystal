import { act, cleanup, render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ChatMonitor } from "./chat-monitor";
import { chatAlertKey, readChatAlert } from "@/services/chat-alert";

const fixture = vi.hoisted(() => ({
  inbox: vi.fn(),
  sound: vi.fn(),
  toast: vi.fn(),
  navigate: vi.fn(),
  watch: vi.fn(),
}));
vi.mock("@/services", () => ({
  useApi: () => ({
    api: { getChatInbox: fixture.inbox, watchChatEvents: fixture.watch },
    mode: "local",
    baseUrl: "chat-fixture",
  }),
}));
vi.mock("@/services/desktop", () => ({ desktop: { playNotificationSound: fixture.sound } }));
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => fixture.navigate,
  useRouterState: () => "/monitor",
}));
vi.mock("sonner", () => ({ toast: fixture.toast }));
const clients: QueryClient[] = [];
const value = {
  actor: { key: "financial", name: "Financeiro", sector: "FIN" },
  rooms: [],
  unread: 1,
  latest_unread_seq: 10,
  latest_room: "Gestão de frota",
};
beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  fixture.inbox.mockResolvedValue(value);
  fixture.sound.mockResolvedValue(undefined);
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  localStorage.clear();
});
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  const view = render(
    <QueryClientProvider client={client}>
      <ChatMonitor />
    </QueryClientProvider>,
  );
  return { client, view };
}

it("toca uma vez por mensagem nova e mantém o aviso para o widget", async () => {
  const { client } = show();
  await waitFor(() => expect(fixture.sound).toHaveBeenCalledTimes(1));
  expect(readChatAlert()).toMatchObject({ unread: 1, room: "Gestão de frota" });
  act(() => client.setQueryData(["chat-inbox", "local", "chat-fixture"], { ...value }));
  expect(fixture.sound).toHaveBeenCalledTimes(1);
  act(() =>
    client.setQueryData(["chat-inbox", "local", "chat-fixture"], {
      ...value,
      unread: 2,
      latest_unread_seq: 11,
    }),
  );
  await waitFor(() => expect(fixture.sound).toHaveBeenCalledTimes(2));
  act(() =>
    client.setQueryData(["chat-inbox", "local", "chat-fixture"], {
      ...value,
      unread: 0,
      latest_unread_seq: 0,
    }),
  );
  await waitFor(() => expect(readChatAlert()).toBeNull());
  expect(fixture.sound).toHaveBeenCalledTimes(2);
});

it("não repete som de mensagem já avisada ao reabrir o aplicativo", async () => {
  const first = show();
  await waitFor(() => expect(fixture.sound).toHaveBeenCalledTimes(1));
  first.view.unmount();
  expect(localStorage.getItem(chatAlertKey)).toBeNull();
  show();
  await waitFor(() => expect(readChatAlert()?.unread).toBe(1));
  expect(fixture.sound).toHaveBeenCalledTimes(1);
});

it("insere a mensagem recebida por WebSocket diretamente na conversa", () => {
  const { client } = show();
  const key = ["chat-room", "local", "chat-fixture", "room-1", 0];
  client.setQueryData(key, { messages: [], requests: [], before: null });
  const receive = fixture.watch.mock.calls[0]?.[0];
  const message = {
    id: "incoming",
    seq: 20,
    client_id: "attempt",
    sender: "other",
    sender_name: "Operador",
    body: "A guia foi enviada",
    kind: "text",
    request_id: null,
    created_at: "2026-11-15T19:00:00Z",
  };
  act(() => receive({ type: "message.created", room_id: "room-1", message }));
  expect(client.getQueryData(key)).toMatchObject({ messages: [message] });
  act(() => receive({ type: "message.created", room_id: "room-1", message }));
  expect(client.getQueryData(key)).toMatchObject({ messages: [message] });
});
