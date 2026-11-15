import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, RefreshCw, Search, ChevronRight } from "lucide-react";
import { useApi } from "@/services";
import {
  type Tariff,
  type TariffCity,
  type TariffQuery,
  tariffLabels,
  tariffTones,
} from "@/services/tariffs";
import { PageBody, TableBox } from "@/components/app/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TariffCitySelect } from "@/components/app/tariff-city-select";
import { TariffDrawer } from "@/components/app/tariff-drawer";
import { fmtBRL, fmtDate, fmtDateTime } from "@/lib/format";

export const Route = createFileRoute("/tarifas")({ component: Tariffs });
function Tariffs() {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [origin, setOrigin] = useState<TariffCity | null>(null);
  const [destination, setDestination] = useState<TariffCity | null>(null);
  const [vehicle, setVehicle] = useState("");
  const [validity, setValidity] = useState<NonNullable<TariffQuery["validity"]>>("vigente");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Tariff | null>(null);
  useEffect(() => {
    const timer = setTimeout(() => setTerm(search), 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => setPage(0), [term, origin?.portal_id, destination?.portal_id, vehicle, validity]);
  const key = ["tariffs", mode, baseUrl];
  const query = {
    search: term,
    origin: origin?.portal_id ?? "",
    destination: destination?.portal_id ?? "",
    vehicle,
    validity,
    page,
    size: 50,
  };
  const q = useQuery({
    queryKey: [...key, query],
    queryFn: () => api.listTariffs(query),
    retry: 0,
    refetchInterval: 60000,
  });
  const sync = useQuery({
    queryKey: ["tariff-sync", mode, baseUrl],
    queryFn: () => api.getTariffSync(),
    retry: 0,
    refetchInterval: (query) => (query.state.data?.state === "running" ? 2000 : 10000),
  });
  const state = sync.data ?? q.data?.sync;
  useEffect(() => {
    if (sync.data?.state === "completed") void qc.invalidateQueries({ queryKey: key });
  }, [sync.data?.completed_at]);
  const refresh = useMutation({
    mutationFn: () => api.refreshTariffs(),
    onSuccess: (value) => {
      qc.setQueryData(["tariff-sync", mode, baseUrl], value);
      void qc.invalidateQueries({ queryKey: key });
    },
  });
  const running = state?.state === "running" || refresh.isPending;
  const money = (value: string | null) => (value === null ? "—" : fmtBRL(Number(value)));
  return (
    <PageBody>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-baseline gap-3">
          <h2 className="text-xl font-semibold">Tarifas e tonelagem</h2>
          <span className="text-xs text-muted-foreground">
            {state?.completed_at
              ? `Atualizado ${fmtDateTime(state.completed_at)}`
              : "Catálogo Novelis"}
          </span>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={running || mode === "demo"}
          onClick={() => refresh.mutate()}
        >
          <RefreshCw className={running ? "animate-spin" : ""} />
          {running ? "Atualizando catálogo…" : "Atualizar do portal"}
        </Button>
      </div>
      {(state?.state === "failed" ||
        state?.state === "interrupted" ||
        refresh.isError ||
        q.isError) && (
        <p
          role="alert"
          className="rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning-foreground"
        >
          {(refresh.error as Error)?.message ?? (q.error as Error)?.message ?? state?.message}
        </p>
      )}
      <div className="grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_200px_180px]">
        <TariffCitySelect label="Origem" value={origin} onChange={setOrigin} />
        <TariffCitySelect label="Destino" value={destination} onChange={setDestination} />
        <div className="space-y-1.5">
          <label className="text-xs font-medium">Veículo</label>
          <Select
            value={vehicle || "all"}
            onValueChange={(value) => setVehicle(value === "all" ? "" : value)}
          >
            <SelectTrigger aria-label="Veículo">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os veículos</SelectItem>
              {(q.data?.vehicles ?? []).filter(Boolean).map((value) => (
                <SelectItem key={value} value={value}>
                  {value}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium">Vigência</label>
          <Select
            value={validity}
              onValueChange={(value) => setValidity(value as NonNullable<TariffQuery["validity"]>)}
          >
            <SelectTrigger aria-label="Vigência">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="todos">Todos os períodos</SelectItem>
              {Object.entries(tariffLabels).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar tarifa, rota, transportadora…"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          {Object.entries(tariffLabels).map(([value, label]) => (
            <span key={value}>
              {label}{" "}
              <strong className="ml-1 font-medium tabular-nums text-foreground">
                {q.data?.counts[value as keyof typeof tariffLabels] ?? 0}
              </strong>
            </span>
          ))}
        </div>
      </div>
      <TableBox maxH="max-h-[calc(100vh-22rem)]">
        <Table className="min-w-[1030px]">
          <TableHeader>
            <TableRow>
              {[
                "Tarifa / rota",
                "Origem / destino",
                "Veículo",
                "R$/t",
                "Capacidade",
                "Total do portal",
                "Vigência",
                "",
              ].map((label, index) => (
                <TableHead key={index}>{label}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {q.isPending ? (
              <TableRow>
                <TableCell colSpan={8} className="py-12 text-center text-muted-foreground">
                  Carregando tarifas…
                </TableCell>
              </TableRow>
            ) : !q.data?.rows.length ? (
              <TableRow>
                <TableCell colSpan={8} className="py-12 text-center text-muted-foreground">
                  {q.isError
                    ? "Não foi possível carregar o catálogo."
                    : state?.total
                      ? "Nenhuma tarifa neste filtro."
                      : "Atualize o catálogo para consultar as tarifas."}
                </TableCell>
              </TableRow>
            ) : (
              q.data.rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer"
                  tabIndex={0}
                  aria-label={`Tarifa ${row.idTarifa}`}
                  onClick={() => setSelected(row)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected(row);
                    }
                  }}
                >
                  <TableCell>
                    <div className="font-medium tabular-nums">{row.idTarifa}</div>
                    <div className="mt-1 text-xs text-muted-foreground">Rota {row.idRota}</div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2 whitespace-nowrap">
                      <span>{row.origem}</span>
                      <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                      <span>{row.destino}</span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{row.transportadora}</div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{row.veiculo}</TableCell>
                  <TableCell className="whitespace-nowrap font-medium tabular-nums">
                    {money(row.tarifaTon)}
                  </TableCell>
                  <TableCell className="tabular-nums">{row.capacidadeTon ?? "—"} t</TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    {money(row.valorTotal)}
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex rounded border px-1.5 py-0.5 text-xs ${tariffTones[row.status]}`}
                    >
                      {tariffLabels[row.status]}
                    </span>
                    <div className="mt-1 whitespace-nowrap text-xs text-muted-foreground">
                      {row.inicio ? fmtDate(row.inicio) : row.inicioPortal || "—"} a{" "}
                      {row.fim ? fmtDate(row.fim) : row.fimPortal || "sem fim"}
                    </div>
                  </TableCell>
                  <TableCell>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableBox>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>
          {q.data?.total.toLocaleString("pt-BR") ?? "—"} tarifas · Página {(q.data?.page ?? 0) + 1}{" "}
          de {Math.max(1, Math.ceil((q.data?.total ?? 0) / 50))}
        </span>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!q.data?.page || q.isFetching}
            onClick={() => setPage((q.data?.page ?? 0) - 1)}
          >
            Anterior
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!q.data || q.isFetching || (q.data.page + 1) * 50 >= q.data.total}
            onClick={() => setPage((q.data?.page ?? 0) + 1)}
          >
            Próxima
          </Button>
        </div>
      </div>
      <TariffDrawer value={selected} onClose={() => setSelected(null)} />
    </PageBody>
  );
}
