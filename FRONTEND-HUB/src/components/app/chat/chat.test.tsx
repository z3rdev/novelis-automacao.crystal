import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  fixture.api.sendChatMessage.mockResolvedValue({ id: "sent" });
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
