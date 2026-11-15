import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { toast } from "sonner";
import { useApi, type HubNotification } from "@/services";
import { Button } from "@/components/ui/button";
import { useOperator } from "./session-gate";
import { useAppDialogs } from "./app-dialogs";
import { NotificationDialog } from "./notification-dialog";
import { Link } from "@tanstack/react-router";

interface NotificationState {
  unread: number; items: HubNotification[]; loading: boolean; error: boolean; saving: boolean;
  refresh(): void; markRead(id: string): void; markAllRead(): void;
}
const NotificationContext = createContext<NotificationState | null>(null);

export function NotificationProvider({ children, inboxOpen = false }: { children: ReactNode; inboxOpen?: boolean }) {
  const { api, mode, baseUrl } = useApi();
  const { session } = useOperator();
  const dialogs = useAppDialogs();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const dismissed = useRef(new Set<string>());
  const query = useQuery({
    queryKey: ["notifications", mode, baseUrl, session?.windows_user, session?.id],
    queryFn: () => api.getNotifications(),
    enabled: mode === "local",
    refetchInterval: 20000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: "always",
    retry: 0,
  });
  const items = query.data ?? [];
  const unread = items.filter((item) => !item.read_at);
  const next = unread.find((item) => !dismissed.current.has(item.id));
  useEffect(() => { dismissed.current.clear(); setSelected(null); }, [baseUrl, session?.id]);
  useEffect(() => {
    if (next && dialogs.active === null && !inboxOpen) {
      setSelected(next.id);
      dismissed.current.add(next.id);
      dialogs.show("notifications");
    }
  }, [next?.id, dialogs.active, dialogs.show, inboxOpen]);
  useEffect(() => { if (inboxOpen) dialogs.hide("notifications"); }, [inboxOpen, dialogs.hide]);
  const mark = useMutation({
    mutationFn: (ids: string[]) => Promise.all(ids.map((id) => api.markNotificationRead(id))),
    onSuccess: (_, ids) => {
      qc.setQueryData<HubNotification[]>(["notifications", mode, baseUrl, session?.windows_user, session?.id], (values) => values?.map((item) => ids.includes(item.id) ? { ...item, read_at: new Date().toISOString() } : item));
      void qc.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (error: Error) => { void qc.invalidateQueries({ queryKey: ["notifications"] }); toast.error(error.message); },
  });
  const changeOpen = (value: boolean) => {
    if (value) dialogs.show("notifications");
    else {
      dialogs.hide("notifications");
    }
  };
  return (
    <NotificationContext.Provider value={{ unread: unread.length, items, loading: query.isLoading,
      error: query.isError, saving: mark.isPending, refresh: () => void query.refetch(),
      markRead: (id) => mark.mutate([id]), markAllRead: () => mark.mutate(unread.map((item) => item.id)) }}>
      {children}
      <NotificationDialog
        open={dialogs.active === "notifications"}
        items={items}
        selectedId={selected}
        onSelect={setSelected}
        onOpenChange={changeOpen}
        onRead={(id) => mark.mutate([id])}
        saving={mark.isPending}
        error={query.isError}
        onRetry={() => void query.refetch()}
        onReadAll={() => mark.mutate(unread.map((item) => item.id))}
      />
    </NotificationContext.Provider>
  );
}

export function NotificationBell() {
  const context = useContext(NotificationContext);
  const { mode } = useApi();
  if (!context || mode !== "local") return null;
  return (
    <Button
      asChild
      size="sm"
      variant="ghost"
      aria-label={`Notificações${context.unread ? `, ${context.unread} não lidas` : ""}`}
    >
      <Link to="/notificacoes">
      <Bell className="h-4 w-4" />
      <span className="hidden lg:inline">Notificações</span>
      {context.unread > 0 && (
        <span className="rounded-full bg-primary px-1.5 text-[10px] text-primary-foreground">
          {context.unread > 99 ? "99+" : context.unread}
        </span>
      )}
      </Link>
    </Button>
  );
}

export function useNotifications() {
  const context = useContext(NotificationContext);
  if (!context) throw new Error("Notificações precisam de NotificationProvider.");
  return context;
}
