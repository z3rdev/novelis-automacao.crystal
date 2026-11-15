import { CheckCheck, MailOpen, Info, AlertTriangle, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fmtDateTime } from "@/lib/format";
import type { HubNotification } from "@/services";

export const noticeLevels = { info: "Comunicado", warning: "Atenção", critical: "Urgente" };

export function NotificationMessage({ item, onRead, saving, onClose }: {
  item: HubNotification; onRead(id: string): void; saving: boolean; onClose?(): void;
}) {
  const Icon = item.severity === "critical" ? ShieldAlert : item.severity === "warning" ? AlertTriangle : Info;
  return <article className="flex min-w-0 flex-col gap-5">
    <div className={`flex items-center gap-2 text-xs font-semibold ${item.severity === "critical" ? "text-destructive" : item.severity === "warning" ? "text-warning-foreground" : "text-info"}`}><Icon className="h-4 w-4" />{noticeLevels[item.severity]}</div>
    <div><h2 className="break-words text-2xl font-semibold tracking-tight text-primary">{item.title}</h2><p className="mt-2 text-xs text-muted-foreground">{item.author} · {fmtDateTime(item.created_at)}</p></div>
    <p className={`${onClose ? "max-h-72 overflow-y-auto" : "min-h-40"} whitespace-pre-wrap break-words text-sm leading-7`}>{item.body}</p>
    <div className="mt-auto border-t pt-5">
      {item.read_at && <p className="mb-4 flex items-center gap-2 text-xs text-info"><MailOpen className="h-4 w-4" />Lida em {fmtDateTime(item.read_at)}</p>}
      <div className="flex flex-wrap gap-2"><Button onClick={() => onRead(item.id)} disabled={saving || Boolean(item.read_at)}><CheckCheck />{item.read_at ? "Mensagem lida" : "Marcar como lida"}</Button>
        {onClose && <Button variant="outline" onClick={onClose}>Fechar</Button>}</div>
    </div>
  </article>;
}
