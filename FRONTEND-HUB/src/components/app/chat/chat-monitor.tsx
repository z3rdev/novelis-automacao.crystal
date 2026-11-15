import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { toast } from "sonner";
import { useApi } from "@/services";
import { desktop } from "@/services/desktop";
import { chatAlertKey } from "@/services/chat-alert";

export function ChatMonitor() {
  const { api, mode, baseUrl } = useApi();
  const navigate = useNavigate();
  const page = useRouterState({ select: (value) => value.location.pathname });
  const previous = useRef(0);
  const inbox = useQuery({
    queryKey: ["chat-inbox", mode, baseUrl],
    queryFn: () => api.getChatInbox(),
    enabled: mode === "local",
    retry: 0,
    refetchInterval: 8000,
    refetchIntervalInBackground: true,
  });
  useEffect(() => {
    if (!inbox.data) return;
    const value = inbox.data;
    const sequence = value.latest_unread_seq ?? value.unread;
    const seenKey = `cargo-hub.chat-seen:${baseUrl}:${value.actor.key}`;
    const seen = Math.max(Number(localStorage.getItem(seenKey) || 0), previous.current);
    const alert = {
      unread: value.unread,
      room: value.latest_room || "Mensagens internas",
      receivedAt: Date.now(),
    };
    localStorage.setItem(chatAlertKey, JSON.stringify(alert));
    window.dispatchEvent(new Event("cargo-hub:chat-alert"));
    if (sequence > seen && value.unread > 0) {
      void desktop.playNotificationSound().catch(() => {});
      localStorage.setItem(seenKey, String(sequence));
    }
    if (sequence > seen && page !== "/conversas") {
      toast("Novas mensagens internas", {
        description: `${inbox.data.unread} mensagem(ns) não lida(s)`,
        action: { label: "Abrir", onClick: () => void navigate({ to: "/conversas" }) },
      });
    }
    previous.current = Math.max(seen, sequence);
  }, [inbox.data, navigate, page, baseUrl]);
  useEffect(
    () => () => {
      localStorage.removeItem(chatAlertKey);
    },
    [],
  );
  return null;
}
