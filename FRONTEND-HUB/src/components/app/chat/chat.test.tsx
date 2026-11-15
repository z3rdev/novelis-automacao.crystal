import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ChatPage } from "./chat-page";
import { ChatDialog } from "./chat-dialog";
import type { GnreRequest } from "@/services/chat";
import { selectOption } from "@/test/select-option";

const fixture = vi.hoisted(() => ({
  api: {
    getChatInbox: vi.fn(),
    getChatDirectory: vi.fn(),
    getChatRoom: vi.fn(),
    sendChatMessage: vi.fn(),
    readChatRoom: vi.fn(),
    createChatRoom: vi.fn(),
    requestGnre: vi.fn(),
    claimGnre: vi.fn(),
    uploadGnre: vi.fn(),
    downloadGnre: vi.fn(),
    listCtes: vi.fn(),
  },
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: fixture.api, mode: "local", baseUrl: "fixture" }),
}));
vi.mock("@/services/desktop", () => ({ desktop: { isDesktop: false, saveFile: vi.fn() } }));
const clients: QueryClient[] = [];
const directory = { operators: [], sectors: [{ code: "FIN", name: "Financeiro" }] };
const request: GnreRequest = {
  id: "request-1",
  cte: "10-10-2789",
  note: "Enviar os dois documentos",
  chamado: "",
  chamado_url: null,
  requested_by: "operator",
  requested_name: "Operador",
  assigned_to: null,
  assigned_name: null,
  state: "waiting",
  guia: null,
  comprovante: null,
  combined: null,
  directory: "share/10-10-2789",
  created_at: "2026-11-15T12:00:00Z",
  updated_at: "2026-11-15T12:00:00Z",
};
const detail = {
  before: null,
  messages: [
    {
      id: "m1",
      seq: 1,
      sender: "operator",
      sender_name: "Operador",
      body: "Solicitação",
      kind: "request",
      request_id: "request-1",
      created_at: "2026-11-15T12:00:00Z",
    },
  ],
  requests: [request],
};
beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, "scrollTo", { configurable: true, value: vi.fn() });
  vi.clearAllMocks();
  fixture.api.getChatInbox.mockResolvedValue({
    actor: { key: "financial", name: "Financeiro", sector: "FIN" },
    unread: 1,
    rooms: [
      {
        id: "room-1",
        title: "Financeiro · Operador",
        target_type: "sector",
        target: "FIN",
        creator: "operator",
        unread: 1,
        last_message: "Solicitação",
        last_message_at: null,
      },
    ],
  });
  fixture.api.getChatDirectory.mockResolvedValue(directory);
  fixture.api.listCtes.mockResolvedValue([
    {
      id: "11-10-433",
      comprovante: "faltando",
      origem: "PA-Ananindeua",
      destino: "SP-Pindamonhangaba",
    },
    { id: "10-10-2789", comprovante: "nao_exige" },
  ]);
  fixture.api.getChatRoom.mockResolvedValue(detail);
  fixture.api.readChatRoom.mockResolvedValue(undefined);
  fixture.api.sendChatMessage.mockImplementation(async (_room, body, client_id) => ({
    ...detail.messages[0],
    id: "sent",
    seq: 2,
    sender: "financial",
    sender_name: "Financeiro",
    kind: "text",
    body,
    client_id,
  }));
  fixture.api.createChatRoom.mockResolvedValue({ id: "room-1" });
  fixture.api.requestGnre.mockResolvedValue({ id: "request-1" });
  fixture.api.uploadGnre.mockResolvedValue(detail);
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
  vi.restoreAllMocks();
});
function show(node = <ChatPage />) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

it("mostra a solicitação e envia texto na conversa selecionada", async () => {
  show();
  expect(
    await screen.findByRole("article", { name: "Documentos do CT-e 10-10-2789" }),
  ).toBeVisible();
  expect(screen.getByText("Guia GNRE")).toBeVisible();
  expect(screen.getByText("Comprovante de pagamento")).toBeVisible();
  fireEvent.change(screen.getByRole("textbox", { name: "Mensagem da conversa" }), {
    target: { value: "Vou providenciar os documentos" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Enviar mensagem" }));
  await waitFor(() =>
    expect(fixture.api.sendChatMessage).toHaveBeenCalledWith(
      "room-1",
      "Vou providenciar os documentos",
      expect.any(String),
    ),
  );
});

it("abre uma solicitação para o Financeiro com o CT-e preenchido", async () => {
  show(
    <ChatDialog
      open
      close={vi.fn()}
      directory={directory}
      gnre
      initialCte="10-10-2789"
      onCreated={vi.fn()}
    />,
  );
  expect(screen.getByLabelText("CT-e")).toHaveValue("10-10-2789");
  fireEvent.click(screen.getByRole("button", { name: "Enviar solicitação" }));
  await waitFor(() => expect(fixture.api.createChatRoom).toHaveBeenCalledWith("sector", "FIN"));
  expect(fixture.api.requestGnre).toHaveBeenCalledWith("room-1", {
    cte: "10-10-2789",
    note: "",
    chamado: "",
    client_id: expect.any(String),
  });
});

it("envia a guia na categoria correta com identificador de repetição", async () => {
  show();
  const input = await screen.findByLabelText("Arquivo de Guia GNRE");
  const file = new File(["unit fixture"], "guia.pdf", { type: "application/pdf" });
  fireEvent.change(input, { target: { files: [file] } });
  await waitFor(() =>
    expect(fixture.api.uploadGnre).toHaveBeenCalledWith(
      "room-1",
      "request-1",
      "guia",
      file,
      expect.any(String),
    ),
  );
});

it("lista os pendentes que exigem documentos e solicita no mesmo chat pelo botão mais", async () => {
  show();
  const plus = await screen.findByRole("button", {
    name: "Solicitar guia e comprovante nesta conversa",
  });
  fireEvent.click(plus);
  await selectOption("CT-es pendentes de GNRE e comprovante", /11-10-433/);
  expect(screen.getByLabelText("CT-e")).toHaveValue("11-10-433");
  expect(
    screen.getByRole("combobox", { name: "CT-es pendentes de GNRE e comprovante" }),
  ).toHaveTextContent("11-10-433");
  expect(screen.queryByRole("option", { name: /10-10-2789/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Enviar solicitação" }));
  await waitFor(() =>
    expect(fixture.api.requestGnre).toHaveBeenCalledWith("room-1", {
      cte: "11-10-433",
      note: "",
      chamado: "",
      client_id: expect.any(String),
    }),
  );
  expect(fixture.api.createChatRoom).not.toHaveBeenCalled();
});

it("oferece somente Financeiro e seus operadores online na nova conversa", async () => {
  show(
    <ChatDialog
      open
      close={vi.fn()}
      gnre={false}
      onCreated={vi.fn()}
      directory={{
        sectors: [
          { code: "FIN", name: "Financeiro" },
          { code: "TI", name: "TI" },
        ],
        operators: [
          {
            key: "fin",
            name: "Financeiro online",
            windows_user: "QA\\fin",
            sector: "FIN",
            online: true,
          },
          {
            key: "off",
            name: "Financeiro offline",
            windows_user: "QA\\off",
            sector: "FIN",
            online: false,
          },
          { key: "ti", name: "TI online", windows_user: "QA\\ti", sector: "TI", online: true },
        ],
      }}
    />,
  );
  fireEvent.keyDown(screen.getByRole("combobox", { name: "Destinatário" }), { key: "ArrowDown" });
  expect(await screen.findByRole("option", { name: "Financeiro" })).toBeVisible();
  expect(screen.queryByRole("option", { name: "TI" })).toBeNull();
  fireEvent.click(screen.getByRole("option", { name: "Financeiro" }));
  await selectOption("Tipo de destinatário", "Operador");
  fireEvent.keyDown(screen.getByRole("combobox", { name: "Destinatário" }), { key: "ArrowDown" });
  expect(await screen.findByRole("option", { name: /Financeiro online/ })).toBeVisible();
  expect(screen.queryByRole("option", { name: /offline|TI online/ })).toBeNull();
});

it("mostra a ausência de operadores online sem abrir uma lista vazia", async () => {
  show(<ChatDialog open close={vi.fn()} gnre={false} onCreated={vi.fn()} directory={directory} />);
  await selectOption("Tipo de destinatário", "Operador");
  expect(screen.getByRole("combobox", { name: "Destinatário" })).toBeDisabled();
  expect(screen.getByRole("combobox", { name: "Destinatário" })).toHaveTextContent(
    "Nenhum operador do Financeiro online",
  );
  expect(screen.getByRole("button", { name: "Abrir conversa" })).toBeDisabled();
});

it("não marca mensagens como lidas com a janela oculta", async () => {
  vi.spyOn(document, "hasFocus").mockReturnValue(true);
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
  show();
  await screen.findByRole("article", { name: "Documentos do CT-e 10-10-2789" });
  expect(fixture.api.readChatRoom).not.toHaveBeenCalled();
});

it("mostra o card reenviado com os documentos já registrados", async () => {
  fixture.api.getChatRoom.mockResolvedValue({
    ...detail,
    messages: [
      ...detail.messages,
      { ...detail.messages[0], id: "attachment", seq: 2, kind: "attachment", body: "Guia enviada" },
      { ...detail.messages[0], id: "resent", seq: 3 },
    ],
    requests: [
      {
        ...request,
        state: "partial",
        guia: {
          id: "saved-guide",
          kind: "guia",
          sha256: "fixture",
          uploaded_name: "Financeiro",
          uploaded_at: "2026-11-15T12:05:00Z",
        },
      },
    ],
  });
  show();
  const cards = await screen.findAllByRole("article", { name: "Documentos do CT-e 10-10-2789" });
  expect(cards).toHaveLength(2);
  for (const card of cards) {
    expect(within(card).getByText("Documentação parcial")).toBeVisible();
    expect(within(card).getByRole("button", { name: "Baixar Guia GNRE" })).toBeVisible();
    expect(within(card).getByText("Aguardando envio")).toBeVisible();
  }
});

it("repete a tentativa com o mesmo identificador e cria outro para um novo envio", async () => {
  const close = vi.fn();
  fixture.api.requestGnre.mockRejectedValueOnce(new Error("Conexão interrompida"));
  show(
    <ChatDialog
      open
      close={close}
      directory={directory}
      gnre
      initialCte="10-10-2789"
      selectedRoom="room-1"
      onCreated={vi.fn()}
    />,
  );
  const send = screen.getByRole("button", { name: "Enviar solicitação" });
  fireEvent.click(send);
  await waitFor(() => expect(fixture.api.requestGnre).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(send).not.toBeDisabled());
  fireEvent.click(send);
  await waitFor(() => expect(close).toHaveBeenCalledTimes(1));
  expect(fixture.api.requestGnre.mock.calls[1]?.[1].client_id).toBe(
    fixture.api.requestGnre.mock.calls[0]?.[1].client_id,
  );
  fireEvent.click(send);
  await waitFor(() => expect(close).toHaveBeenCalledTimes(2));
  expect(fixture.api.requestGnre.mock.calls[2]?.[1].client_id).not.toBe(
    fixture.api.requestGnre.mock.calls[0]?.[1].client_id,
  );
});

it("mostra a mensagem como enviando enquanto a confirmação está pendente", async () => {
  let confirm!: (message: unknown) => void;
  fixture.api.sendChatMessage.mockImplementation(
    () =>
      new Promise((resolve) => {
        confirm = resolve;
      }),
  );
  show();
  await screen.findByRole("article", { name: "Documentos do CT-e 10-10-2789" });
  fireEvent.change(screen.getByRole("textbox", { name: "Mensagem da conversa" }), {
    target: { value: "Já estou providenciando" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Enviar mensagem" }));
  expect(await screen.findByText("Enviando…")).toBeVisible();
  expect(within(screen.getByRole("log")).getByText("Já estou providenciando")).toBeVisible();
  const clientId = fixture.api.sendChatMessage.mock.calls[0]?.[2];
  confirm({
    ...detail.messages[0],
    id: "confirmed",
    seq: 2,
    kind: "text",
    sender: "financial",
    sender_name: "Financeiro",
    body: "Já estou providenciando",
    client_id: clientId,
  });
  await waitFor(() => expect(screen.queryByText("Enviando…")).toBeNull());
  expect(screen.getAllByText("Já estou providenciando")).toHaveLength(1);
});

it("mantém a confirmação WebSocket quando a resposta HTTP falha depois da gravação", async () => {
  let fail!: (error: Error) => void;
  fixture.api.sendChatMessage.mockImplementation(
    () =>
      new Promise((_resolve, reject) => {
        fail = reject;
      }),
  );
  show();
  await screen.findByRole("article", { name: "Documentos do CT-e 10-10-2789" });
  fireEvent.change(screen.getByRole("textbox", { name: "Mensagem da conversa" }), {
    target: { value: "Confirmada" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Enviar mensagem" }));
  await screen.findByText("Enviando…");
  const clientId = fixture.api.sendChatMessage.mock.calls[0]?.[2];
  act(() =>
    clients.at(-1)!.setQueryData(["chat-room", "local", "fixture", "room-1", 0], {
      ...detail,
      messages: [
        ...detail.messages,
        {
          ...detail.messages[0],
          id: "received",
          seq: 2,
          sender: "financial",
          kind: "text",
          body: "Confirmada",
          client_id: clientId,
        },
      ],
    }),
  );
  fail(new Error("Resposta interrompida"));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Enviar mensagem" })).toBeDisabled(),
  );
  await waitFor(() =>
    expect(screen.getByRole("textbox", { name: "Mensagem da conversa" })).toHaveValue(""),
  );
  expect(screen.queryByText("Falha no envio. Tente novamente.")).toBeNull();
  expect(within(screen.getByRole("log")).getByText("Confirmada")).toBeVisible();
});
