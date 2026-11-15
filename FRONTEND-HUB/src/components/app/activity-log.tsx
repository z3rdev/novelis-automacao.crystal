import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUp, ChevronRight, Pause, Play, Search, Trash2 } from "lucide-react";
import { useApi, type LogEntry } from "@/services";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fmtDate, fmtTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { eventCte, eventMessage, logCategory, logLevels } from "./log-presentation";
import { LogDetail } from "./log-detail";

export function ActivityLog({ onLatestXml }: { onLatestXml?(entry: LogEntry | undefined): void }) {
  const { api, mode, baseUrl } = useApi();
  const [paused, setPaused] = useState(false);
  const [frozen, setFrozen] = useState<LogEntry[]>([]);
  const [following, setFollowing] = useState(true);
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState("operation");
  const [clearedAt, setClearedAt] = useState(0);
  const [selected, setSelected] = useState<LogEntry | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const anchor = useRef<{ id: string; offset: number } | null>(null);
  const query = useQuery({
    queryKey: ["logs", mode, baseUrl],
    queryFn: () => api.listLogs(),
    refetchInterval: 1500,
    refetchOnWindowFocus: true,
    retry: 0,
  });
  const entries = useMemo(
    () =>
      [...(query.data ?? [])].sort(
        (a, b) =>
          (Date.parse(b.time) || 0) - (Date.parse(a.time) || 0) || Number(b.id) - Number(a.id),
      ),
    [query.data],
  );
  useEffect(() => {
    onLatestXml?.(entries.find((entry) => entry.source.startsWith("xml_sefaz.")));
  }, [entries, onLatestXml]);
  const logs = useMemo(
    () =>
      (paused ? frozen : entries).filter(
        (item) =>
          Number(item.id) > clearedAt &&
          (level === "all" ||
            (level === "operation" && item.severity !== "debug") ||
            item.severity === level) &&
          `${item.message} ${item.source} ${item.details ?? ""}`
            .toLocaleLowerCase("pt-BR")
            .includes(search.toLocaleLowerCase("pt-BR")),
      ),
    [entries, paused, frozen, clearedAt, level, search],
  );
  const groups = useMemo(() => {
    const result: { date: string; items: LogEntry[] }[] = [];
    for (const item of logs) {
      const date = fmtDate(item.time);
      if (result.at(-1)?.date !== date) result.push({ date, items: [] });
      result.at(-1)!.items.push(item);
    }
    return result;
  }, [logs]);
  useLayoutEffect(() => {
    const element = box.current;
    if (!element) return;
    if (following) element.scrollTop = 0;
    else if (anchor.current) {
      const item = Array.from(element.querySelectorAll<HTMLElement>("[data-log-id]")).find(
        (row) => row.dataset["logId"] === anchor.current?.id,
      );
      if (item)
        element.scrollTop +=
          item.getBoundingClientRect().top -
          element.getBoundingClientRect().top -
          anchor.current.offset;
    }
  }, [logs, following]);
  return (
    <section
      className="overflow-hidden rounded-lg border bg-card"
      aria-label="Atividade da automação"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold">Atividade da automação</h2>
          <span className="text-xs tabular-nums text-muted-foreground">{logs.length} eventos</span>
        </div>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              query.isError ? "bg-amber-500" : paused ? "bg-slate-400" : "bg-teal-500",
            )}
          />
          {query.isError ? "Sem conexão" : paused ? "Pausado" : "Ao vivo"}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2 border-b px-5 py-3">
        <div className="relative min-w-48 flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            aria-label="Buscar eventos"
            placeholder="Buscar evento, CT-e ou mensagem…"
            className="h-9 pl-9"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <Select value={level} onValueChange={setLevel}>
          <SelectTrigger className="h-9 w-40" aria-label="Filtrar eventos">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="operation">Operação</SelectItem>
            <SelectItem value="all">Todos os níveis</SelectItem>
            {Object.entries(logLevels).map(([key, value]) => (
              <SelectItem key={key} value={key}>
                {value.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            if (!paused) setFrozen(entries);
            setPaused((value) => !value);
          }}
        >
          {paused ? <Play /> : <Pause />}
          {paused ? "Retomar" : "Pausar"}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          aria-label="Limpar visualização"
          onClick={() =>
            setClearedAt(Math.max(clearedAt, ...entries.map((entry) => Number(entry.id))))
          }
        >
          <Trash2 className="h-4 w-4" />
          <span className="hidden xl:inline">Limpar visualização</span>
        </Button>
      </div>
      {query.isError && (
        <p role="alert" className="border-b px-5 py-3 text-sm text-destructive">
          Não foi possível atualizar os eventos.
        </p>
      )}
      <div
        ref={box}
        className="relative max-h-[55vh] min-h-48 overflow-y-auto"
        onScroll={() => {
          const element = box.current;
          if (!element) return;
          setFollowing(element.scrollTop < 40);
          const top = element.getBoundingClientRect().top;
          const item = Array.from(element.querySelectorAll<HTMLElement>("[data-log-id]")).find(
            (row) => row.getBoundingClientRect().bottom > top + 32,
          );
          anchor.current = item
            ? { id: item.dataset["logId"]!, offset: item.getBoundingClientRect().top - top }
            : null;
        }}
      >
        {groups.map((group) => (
          <div key={group.date}>
            <div className="sticky top-0 z-10 border-y bg-muted/90 px-5 py-2 text-[11px] font-medium text-muted-foreground backdrop-blur-sm">
              {group.date}
            </div>
            {group.items.map((item) => {
              const style = logLevels[item.severity],
                Icon = style.icon,
                cte = eventCte(item);
              return (
                <button
                  key={item.id}
                  data-log-id={item.id}
                  className="group flex w-full items-start gap-3 border-b border-border/60 px-5 py-3 text-left transition-colors hover:bg-muted/30 focus-visible:outline-2 focus-visible:outline-teal-500"
                  onClick={() => setSelected(item)}
                  aria-label={`Ver evento: ${item.message}`}
                >
                  <time className="w-16 shrink-0 pt-0.5 text-xs tabular-nums text-muted-foreground">
                    {fmtTime(item.time)}
                  </time>
                  <span
                    className={cn(
                      "flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                      style.background,
                      style.color,
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="mb-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                      <span>{logCategory(item.source)}</span>
                      {cte && <span className="font-mono">{cte}</span>}
                      {["erro", "aviso"].includes(item.severity) && (
                        <span className={style.color}>{style.label}</span>
                      )}
                    </span>
                    <span className="line-clamp-2 break-words text-sm leading-5 [overflow-wrap:anywhere]">
                      {eventMessage(item)}
                    </span>
                  </span>
                  <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground/40 group-hover:text-primary" />
                </button>
              );
            })}
          </div>
        ))}
        {!logs.length && (
          <p className="py-16 text-center text-sm text-muted-foreground">
            {query.isLoading ? "Carregando eventos…" : "Nenhum evento para exibir."}
          </p>
        )}
      </div>
      {!following && logs.length > 0 && (
        <div className="flex justify-end border-t px-5 py-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setFollowing(true);
              if (box.current) box.current.scrollTop = 0;
            }}
          >
            <ArrowUp />
            Ir para recentes
          </Button>
        </div>
      )}
      <LogDetail entry={selected} onClose={() => setSelected(null)} />
    </section>
  );
}
