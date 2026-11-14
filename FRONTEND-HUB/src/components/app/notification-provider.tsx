import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/services";
import { Button } from "@/components/ui/button";
import { useOperator } from "./session-gate";
import { useAppDialogs } from "./app-dialogs";
import { NotificationDialog } from "./notification-dialog";

const NotificationContext = createContext<{ unread: number; show(): void } | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { api, mode, baseUrl } = useApi();
  const { session } = useOperator();
  const dialogs = useAppDialogs();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const dismissed = useRef(new Set<string>());
  const query = useQuery({
    queryKey: ["notifications", mode, baseUrl, session?.windows_user],
    queryFn: () => api.getNotifications(),
    enabled: mode === "local",
    refetchInterval: 20000,
    retry: 0,
  });
  const items = query.data ?? [];
  const unread = items.filter((item) => !item.read_at);
  const next = unread.find((item) => !dismissed.current.has(item.id));
  useEffect(() => {
    if (next && dialogs.active === null) {
      setSelected(next.id);
      dialogs.show("notifications");
    }
  }, [next?.id, dialogs.active, dialogs.show]);
  const mark = useMutation({
    mutationFn: (id: string) => api.markNotificationRead(id),
    onSuccess: (_, id) => {
      setSelected(unread.find((item) => item.id !== id)?.id ?? id);
      void qc.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const changeOpen = (value: boolean) => {
    if (value) dialogs.show("notifications");
    else {
      unread.forEach((item) => dismissed.current.add(item.id));
      dialogs.hide("notifications");
    }
  };
  return (
    <NotificationContext.Provider value={{ unread: unread.length, show: () => changeOpen(true) }}>
      {children}
      <NotificationDialog
        open={dialogs.active === "notifications"}
        items={items}
        selectedId={selected}
        onSelect={setSelected}
        onOpenChange={changeOpen}
        onRead={(id) => mark.mutate(id)}
        saving={mark.isPending}
        error={query.isError}
        onRetry={() => void query.refetch()}
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
      size="sm"
      variant="ghost"
      onClick={context.show}
      aria-label={`Notificações${context.unread ? `, ${context.unread} não lidas` : ""}`}
    >
      <Bell className="h-4 w-4" />
      <span className="hidden lg:inline">Notificações</span>
      {context.unread > 0 && (
        <span className="rounded-full bg-primary px-1.5 text-[10px] text-primary-foreground">
          {context.unread > 99 ? "99+" : context.unread}
        </span>
      )}
    </Button>
  );
}
