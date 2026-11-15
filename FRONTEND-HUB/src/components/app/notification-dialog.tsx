import { Bell, CheckCheck } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { HubNotification } from "@/services";
import { fmtDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

import { NotificationMessage } from "./notification-message";
export { noticeLevels } from "./notification-message";

interface Props {
  open: boolean;
  items: HubNotification[];
  selectedId: string | null;
  onSelect(id: string): void;
  onOpenChange(open: boolean): void;
  onRead(id: string): void;
  saving: boolean;
  error: boolean;
  onRetry(): void;
  onReadAll?(): void;
}

export function NotificationDialog({
  open,
  items,
  selectedId,
  onSelect,
  onOpenChange,
  onRead,
  saving,
  error,
  onRetry,
  onReadAll,
}: Props) {
  const selected =
    items.find((item) => item.id === selectedId) ?? items.find((item) => !item.read_at) ?? items[0];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto rounded-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notificações
          </DialogTitle>
          <DialogDescription>Comunicados da equipe de desenvolvimento. {items.filter((item) => !item.read_at).length} não lida(s).</DialogDescription>
        </DialogHeader>
        {onReadAll && items.some((item) => !item.read_at) && <Button className="justify-self-start" variant="outline" size="sm" disabled={saving} onClick={onReadAll}><CheckCheck />Marcar todas como lidas</Button>}
        {error && (
          <div role="alert" className="space-y-2 text-sm text-destructive">
            <p>Não foi possível consultar o servidor de notificações ou o cache de leitura.</p>
            <Button size="sm" variant="outline" onClick={onRetry}>
              Tentar novamente
            </Button>
          </div>
        )}
        {!items.length && !error && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Nenhuma notificação disponível.
          </p>
        )}
        {selected && (
          <div className="grid min-w-0 gap-5 sm:grid-cols-[220px_minmax(0,1fr)]">
            <nav
              aria-label="Lista de notificações"
              className="flex max-h-40 flex-col gap-1 overflow-y-auto sm:max-h-96"
            >
              {items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => onSelect(item.id)}
                  aria-current={item.id === selected.id ? "true" : undefined}
                  className={cn(
                    "rounded-lg border p-3 text-left text-sm",
                    item.id === selected.id
                      ? "border-primary/30 bg-accent"
                      : "border-transparent hover:bg-muted",
                  )}
                >
                  <span className="flex items-start gap-2">
                    {!item.read_at && (
                      <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-teal-500" />
                    )}
                    <span className="break-words font-medium">{item.title}</span>
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {fmtDateTime(item.created_at)}
                  </span>
                </button>
              ))}
            </nav>
            <NotificationMessage item={selected} onRead={onRead} saving={saving} onClose={() => onOpenChange(false)} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
