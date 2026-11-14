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

export const noticeLevels = { info: "Comunicado", warning: "Atenção", critical: "Urgente" };

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
          <DialogDescription>Comunicados da equipe de desenvolvimento.</DialogDescription>
        </DialogHeader>
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
            <article className="flex min-w-0 flex-col gap-3">
              <p
                className={cn(
                  "text-xs font-semibold",
                  selected.severity === "critical"
                    ? "text-destructive"
                    : selected.severity === "warning"
                      ? "text-warning"
                      : "text-muted-foreground",
                )}
              >
                {noticeLevels[selected.severity]}
              </p>
              <h3 className="break-words text-xl font-semibold text-primary">{selected.title}</h3>
              <p className="text-xs text-muted-foreground">
                {selected.author} · {fmtDateTime(selected.created_at)}
              </p>
              <p className="max-h-72 overflow-y-auto whitespace-pre-wrap break-words text-sm leading-relaxed">
                {selected.body}
              </p>
              <div className="mt-auto flex flex-wrap items-center gap-2 pt-4">
                <Button
                  onClick={() => onRead(selected.id)}
                  disabled={saving || Boolean(selected.read_at)}
                >
                  <CheckCheck />
                  {selected.read_at ? "Mensagem lida" : "Marcar como lida"}
                </Button>
                <Button variant="outline" onClick={() => onOpenChange(false)}>
                  Fechar
                </Button>
              </div>
            </article>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
