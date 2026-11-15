import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { CheckCheck, RefreshCw, Mail, Search, Inbox } from "lucide-react";
import { PageBody } from "@/components/app/page";
import { useNotifications } from "@/components/app/notification-provider";
import { NotificationMessage, noticeLevels } from "@/components/app/notification-message";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fmtDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/notificacoes")({
  component: Notifications,
  head: () => ({ meta: [{ title: "Notificações · Cargo Hub" }] }),
});

function Notifications() {
  const notices = useNotifications();
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const items = notices.items.filter(
    (item) =>
      (filter === "all" || !item.read_at) &&
      `${item.title} ${item.body}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
  );
  const selected =
    items.find((item) => item.id === selectedId) ?? items.find((item) => !item.read_at) ?? items[0];
  useEffect(() => {
    if (selected) setSelectedId(selected.id);
  }, [selected?.id]);
  return (
    <PageBody>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h2 className="text-xl font-semibold">Notificações</h2>
          <span className="text-sm text-muted-foreground">{notices.unread} não lidas</span>
        </div>
        <Button variant="outline" size="sm" onClick={notices.refresh}>
          <RefreshCw className={notices.loading ? "animate-spin" : ""} />
          Atualizar
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant={filter === "all" ? "default" : "outline"}
          size="sm"
          onClick={() => setFilter("all")}
        >
          Todas ({notices.items.length})
        </Button>
        <Button
          variant={filter === "unread" ? "default" : "outline"}
          size="sm"
          onClick={() => setFilter("unread")}
        >
          <Mail />
          Não lidas ({notices.unread})
        </Button>
        <Button
          className="ml-auto"
          variant="ghost"
          size="sm"
          disabled={!notices.unread || notices.saving}
          onClick={notices.markAllRead}
        >
          <CheckCheck />
          Marcar todas como lidas
        </Button>
      </div>
      {notices.error && (
        <p
          role="alert"
          className="rounded-lg border border-amber-500/25 bg-amber-500/5 p-4 text-sm"
        >
          O servidor de notificações está indisponível. A consulta será repetida automaticamente.
        </p>
      )}
      <section className="grid min-h-[500px] min-w-0 overflow-hidden rounded-lg border bg-card lg:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="min-w-0 border-b bg-card lg:border-b-0 lg:border-r">
          <div className="relative border-b p-4">
            <Search className="absolute left-7 top-6 h-4 w-4 text-muted-foreground" />
            <Input
              aria-label="Buscar notificações"
              className="bg-card pl-9"
              placeholder="Buscar comunicado…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <nav aria-label="Comunicados" className="max-h-72 overflow-y-auto lg:max-h-[65vh]">
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => setSelectedId(item.id)}
                aria-current={selected?.id === item.id ? "true" : undefined}
                className={cn(
                  "flex w-full gap-3 border-b px-5 py-4 text-left transition-colors hover:bg-muted/50",
                  selected?.id === item.id && "border-l-[3px] border-l-teal-500 bg-teal-500/5",
                )}
              >
                <span
                  className={cn(
                    "mt-1.5 h-2 w-2 shrink-0 rounded-full",
                    item.read_at ? "bg-muted-foreground/20" : "bg-teal-500",
                  )}
                />
                <span className="min-w-0">
                  <span className="mb-2 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {noticeLevels[item.severity]}
                  </span>
                  <span className="block break-words text-sm font-medium">{item.title}</span>
                  <span className="mt-2 block text-xs text-muted-foreground">
                    {fmtDateTime(item.created_at)}
                  </span>
                </span>
              </button>
            ))}
            {!items.length && (
              <p className="p-6 text-center text-xs text-muted-foreground">
                {notices.loading ? "Carregando comunicados…" : "Nenhum comunicado nesta lista."}
              </p>
            )}
          </nav>
        </aside>
        <div className="min-w-0 p-6 lg:p-9">
          {selected ? (
            <NotificationMessage
              item={selected}
              onRead={notices.markRead}
              saving={notices.saving}
            />
          ) : (
            <div className="flex h-full min-h-80 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
              <Inbox className="h-6 w-6 opacity-50" />
              <h3 className="text-sm font-medium">
                {notices.loading
                  ? "Carregando notificações…"
                  : filter === "unread"
                    ? "Nenhuma notificação não lida"
                    : "Nenhuma notificação disponível"}
              </h3>
            </div>
          )}
        </div>
      </section>
    </PageBody>
  );
}
