import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  MessageSquarePlus,
  FilePlus2,
  Search,
  Send,
  RefreshCw,
  ChevronLeft,
  Plus,
} from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/services";
import type { ChatActor, ChatDetail, ChatRoom } from "@/services/chat";
import { mergeChatSnapshot, mergeChatMessage } from "@/services/chat-cache";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { fmtDateTime } from "@/lib/format";
import { PageBody } from "../page";
import { GnreCard } from "./gnre-card";
import { ChatDialog } from "./chat-dialog";
import "./chat.css";

export function ChatPage({
  initialCte = "",
  initialRoom,
}: {
  initialCte?: string;
  initialRoom?: string;
}) {
  const { api, mode, baseUrl } = useApi();
  const [selected, setSelected] = useState(initialRoom);
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<"conversation" | "gnre" | null>(initialCte ? "gnre" : null);
  const [requestInRoom, setRequestInRoom] = useState(false);
  const inbox = useQuery({
    queryKey: ["chat-inbox", mode, baseUrl],
    queryFn: () => api.getChatInbox(),
    refetchInterval: 8000,
    retry: 0,
  });
  const directory = useQuery({
    queryKey: ["chat-directory", mode, baseUrl],
    queryFn: () => api.getChatDirectory(),
    refetchInterval: 8000,
    refetchOnWindowFocus: "always",
    retry: 0,
  });
  const room = inbox.data?.rooms.find((value) => value.id === selected) ?? inbox.data?.rooms[0];
  const rooms = (inbox.data?.rooms ?? []).filter((value) =>
    `${value.title} ${value.last_message ?? ""}`
      .toLocaleLowerCase("pt-BR")
      .includes(search.toLocaleLowerCase("pt-BR")),
  );
  return (
    <PageBody className="chat-page space-y-0">
      <div className="chat-page-heading">
        <h2>Mensagens</h2>
        <div>
          <Button
            variant="outline"
            onClick={() => {
              void directory.refetch();
              setRequestInRoom(false);
              setDialog("gnre");
            }}
          >
            <FilePlus2 />
            Solicitar GNRE
          </Button>
          <Button
            onClick={() => {
              void directory.refetch();
              setRequestInRoom(false);
              setDialog("conversation");
            }}
          >
            <MessageSquarePlus />
            Nova conversa
          </Button>
        </div>
      </div>
      {(inbox.isError || directory.isError) && (
        <div className="chat-error" role="alert">
          {(inbox.error ?? directory.error)?.message}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              void inbox.refetch();
              void directory.refetch();
            }}
          >
            <RefreshCw />
            Tentar novamente
          </Button>
        </div>
      )}
      <div className="chat-workspace">
        <aside className="chat-conversations" aria-label="Conversas">
          <div className="chat-search">
            <Search />
            <Input
              aria-label="Buscar conversa"
              placeholder="Buscar conversa…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="chat-room-list">
            {rooms.map((value) => (
              <button
                type="button"
                key={value.id}
                className="chat-room"
                data-selected={room?.id === value.id}
                onClick={() => setSelected(value.id)}
              >
                <span className="chat-room-avatar">{value.title.slice(0, 2).toUpperCase()}</span>
                <span className="chat-room-text">
                  <strong>{value.title}</strong>
                  <small>{value.last_message ?? "Inicie a conversa"}</small>
                </span>
                {value.unread > 0 && (
                  <span className="chat-unread" aria-label={`${value.unread} não lidas`}>
                    {value.unread}
                  </span>
                )}
              </button>
            ))}
            {!rooms.length && (
              <p className="chat-empty-list">
                {inbox.isPending ? "Carregando conversas…" : "Nenhuma conversa"}
              </p>
            )}
          </div>
        </aside>
        {room && inbox.data ? (
          <Conversation
            key={room.id}
            room={room}
            actor={inbox.data.actor}
            onRequest={() => {
              setRequestInRoom(true);
              setDialog("gnre");
            }}
          />
        ) : (
          <section className="chat-empty">
            <MessageSquarePlus />
            <p>Selecione uma conversa ou fale com um setor.</p>
          </section>
        )}
      </div>
      {dialog && (
        <ChatDialog
          open
          close={() => setDialog(null)}
          directory={directory.data}
          initialCte={initialCte}
          gnre={dialog === "gnre"}
          {...(requestInRoom && room ? { selectedRoom: room.id } : {})}
          onCreated={setSelected}
        />
      )}
    </PageBody>
  );
}

function Conversation({
  room,
  actor,
  onRequest,
}: {
  room: ChatRoom;
  actor: ChatActor;
  onRequest(): void;
}) {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const [before, setBefore] = useState<number>();
  const [text, setText] = useState("");
  const attempt = useRef<{ text: string; id: string } | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const latestKey = ["chat-room", mode, baseUrl, room.id, 0];
  const detail = useQuery({
    queryKey: ["chat-room", mode, baseUrl, room.id, before ?? 0],
    queryFn: async () => {
      const snapshot = await api.getChatRoom(room.id, before);
      const cached = qc.getQueryData<ChatDetail>([
        "chat-room",
        mode,
        baseUrl,
        room.id,
        before ?? 0,
      ]);
      return mergeChatSnapshot(snapshot, cached);
    },
    refetchInterval: before ? false : 3000,
    retry: 0,
  });
  const latest = detail.data?.messages.filter((message) => !message.delivery).at(-1)?.seq ?? 0;
  const send = useMutation({
    onMutate: async (body: string) => {
      await qc.cancelQueries({ queryKey: latestKey });
      if (!attempt.current || attempt.current.text !== body)
        attempt.current = { text: body, id: crypto.randomUUID() };
      const clientId = attempt.current.id;
      setBefore(undefined);
      qc.setQueryData<ChatDetail>(latestKey, (current) => {
        const value = current ?? { messages: [], requests: [], before: null };
        return mergeChatMessage(value, {
          id: `pending:${clientId}`,
          client_id: clientId,
          seq: (value.messages.at(-1)?.seq ?? 0) + 1,
          sender: actor.key,
          sender_name: actor.name,
          body,
          kind: "text",
          request_id: null,
          created_at: new Date().toISOString(),
          delivery: "sending",
        });
      });
      return clientId;
    },
    mutationFn: (body: string) => {
      if (!attempt.current || attempt.current.text !== body)
        attempt.current = { text: body, id: crypto.randomUUID() };
      return api.sendChatMessage(room.id, body, attempt.current.id);
    },
    onSuccess: (message, body) => {
      qc.setQueryData<ChatDetail>(latestKey, (current) =>
        current ? mergeChatMessage(current, message) : current,
      );
      setText((value) => (value.trim() === body ? "" : value));
      attempt.current = null;
      setBefore(undefined);
      void qc.invalidateQueries({ queryKey: ["chat-room", mode, baseUrl, room.id] });
      void qc.invalidateQueries({ queryKey: ["chat-inbox"] });
    },
    onError: (error: Error, body, clientId) => {
      const confirmed = qc
        .getQueryData<ChatDetail>(latestKey)
        ?.messages.find((message) => message.client_id === clientId && !message.delivery);
      if (confirmed) {
        setText((value) => (value.trim() === body ? "" : value));
        attempt.current = null;
        return;
      }
      qc.setQueryData<ChatDetail>(
        latestKey,
        (current) =>
          current && {
            ...current,
            messages: current.messages.map((message) =>
              message.delivery && message.client_id === clientId
                ? { ...message, delivery: "failed" }
                : message,
            ),
          },
      );
      toast.error(error.message);
    },
  });
  useEffect(() => {
    const read = () => {
      if (latest && !before && document.visibilityState === "visible" && document.hasFocus()) {
        void api
          .readChatRoom(room.id, latest)
          .then(() => qc.invalidateQueries({ queryKey: ["chat-inbox", mode, baseUrl] }))
          .catch(() => {});
      }
    };
    read();
    window.addEventListener("focus", read);
    document.addEventListener("visibilitychange", read);
    return () => {
      window.removeEventListener("focus", read);
      document.removeEventListener("visibilitychange", read);
    };
  }, [api, latest, room.id, before, qc, mode, baseUrl]);
  useEffect(() => {
    if (!before) scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: "smooth" });
  }, [latest, before, detail.data?.messages.length]);
  const displayedRequests = new Set<string>();
  return (
    <section className="chat-conversation" aria-label={`Conversa com ${room.title}`}>
      <header className="chat-conversation-header">
        <div>
          <h3>{room.title}</h3>
          <small>
            {room.target_type === "sector" ? "Conversa com o setor" : "Conversa direta"}
          </small>
        </div>
        <Button variant="outline" size="sm" onClick={onRequest}>
          <FilePlus2 />
          Solicitar GNRE
        </Button>
      </header>
      {detail.isError && (
        <div className="chat-error" role="alert">
          {detail.error.message}
          <Button variant="ghost" size="sm" onClick={() => void detail.refetch()}>
            Atualizar
          </Button>
        </div>
      )}
      {detail.data?.delivery_warning && (
        <p className="chat-error" role="status">
          {detail.data.delivery_warning}
        </p>
      )}
      <div
        className="chat-timeline"
        ref={scroll}
        role="log"
        aria-label="Mensagens da conversa"
        aria-live="polite"
      >
        <div className="chat-pagination">
          {detail.data?.before && (
            <Button variant="ghost" size="sm" onClick={() => setBefore(detail.data!.before!)}>
              <ChevronLeft />
              Mensagens anteriores
            </Button>
          )}
          {before && (
            <Button variant="ghost" size="sm" onClick={() => setBefore(undefined)}>
              Voltar às recentes
            </Button>
          )}
        </div>
        {detail.data?.messages.map((message) => {
          const request = detail.data.requests.find((item) => item.id === message.request_id);
          const showRequest =
            request && (message.kind === "request" || !displayedRequests.has(request.id));
          if (request) displayedRequests.add(request.id);
          return (
            <div key={message.id} className="chat-message" data-own={message.sender === actor.key}>
              <div className="chat-message-meta">
                <strong>{message.sender_name}</strong>
                <time dateTime={message.created_at}>{fmtDateTime(message.created_at)}</time>
              </div>
              <div className="chat-message-body">
                {showRequest ? <GnreCard value={request} room={room.id} /> : <p>{message.body}</p>}
                {message.delivery && (
                  <small role="status">
                    {message.delivery === "sending"
                      ? "Enviando…"
                      : "Falha no envio. Tente novamente."}
                  </small>
                )}
              </div>
            </div>
          );
        })}
        {!detail.isPending && !detail.data?.messages.length && (
          <p className="chat-empty-list">Envie a primeira mensagem.</p>
        )}
      </div>
      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          if (text.trim() && !send.isPending) send.mutate(text.trim());
        }}
      >
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onRequest}
          aria-label="Solicitar guia e comprovante nesta conversa"
          title="Solicitar guia e comprovante"
        >
          <Plus />
        </Button>
        <Textarea
          aria-label="Mensagem da conversa"
          placeholder="Escreva uma mensagem…"
          value={text}
          maxLength={8000}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              if (text.trim() && !send.isPending) send.mutate(text.trim());
            }
          }}
        />
        <Button
          type="submit"
          size="icon"
          aria-label="Enviar mensagem"
          disabled={!text.trim() || send.isPending}
        >
          <Send />
        </Button>
      </form>
    </section>
  );
}
