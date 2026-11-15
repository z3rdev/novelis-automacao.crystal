import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Stethoscope } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/services";
import type { DiagnosticRequest } from "@/services/remote-diagnostics";
import { desktop } from "@/services/desktop";
import { fmtDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageBody, Section, TableBox } from "../page";
import { DiagnosticReportPanel, DiagnosticStatePill } from "./diagnostic-report";
import "./diagnostics.css";
import { AppSelect } from "../fields/app-select";

export function DiagnosticCenter() {
  const { api, mode, baseUrl } = useApi();
  const client = useQueryClient();
  const [device, setDevice] = useState("");
  const [maxRuns, setMaxRuns] = useState(10);
  const [days, setDays] = useState(7);
  const [selected, setSelected] = useState<string | null>(null);
  const key = ["developer-diagnostics", mode, baseUrl];
  const developer = useQuery({
    queryKey: ["developer-config", mode, baseUrl],
    queryFn: () => api.getDeveloperConfig(),
    enabled: mode === "local",
    retry: 0,
  });
  const allowed = mode === "local" && developer.data?.enabled === true;
  const agents = useQuery({
    queryKey: [...key, "agents"],
    queryFn: () => api.getDiagnosticAgents(),
    enabled: allowed,
    refetchInterval: 15000,
    retry: 0,
  });
  const inventory = useQuery({
    queryKey: ["developer-monitor", mode, baseUrl],
    queryFn: () => api.getDeveloperMonitor(),
    enabled: allowed,
    refetchInterval: 30000,
    retry: 0,
  });
  const requests = useQuery({
    queryKey: [...key, "requests"],
    queryFn: () => api.listDiagnosticRequests(),
    enabled: allowed,
    refetchInterval: 5000,
    retry: 0,
  });
  const detail = useQuery({
    queryKey: [...key, "detail", selected],
    queryFn: () => api.getDiagnosticRequest(selected!),
    enabled: allowed && !!selected,
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.state ?? "") ? 2000 : false,
    retry: 0,
  });
  const create = useMutation({
    mutationFn: () => api.requestDiagnostic(device, maxRuns, days),
    onSuccess: (value) => {
      setSelected(value.id);
      void client.invalidateQueries({ queryKey: key });
      toast.success("Diagnóstico solicitado");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const download = useMutation({
    mutationFn: async (value: DiagnosticRequest) => {
      await desktop.saveFile(
        `CargoHub-Diagnostico-${value.computer_name}-${value.id.slice(0, 8)}.json`,
        new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
      );
    },
    onError: (error: Error) => toast.error(error.message),
  });
  if (!allowed)
    return (
      <PageBody>
        <Section title="Central de diagnóstico">
          <p className="text-sm text-muted-foreground">
            {developer.isLoading
              ? "Verificando acesso…"
              : "Acesso exclusivo do desenvolvedor neste computador."}
          </p>
        </Section>
      </PageBody>
    );
  const known = new Map<string, { id: string; name: string; kind: string }>(
    (inventory.data?.devices ?? []).map((item) => [
      item.id,
      {
        id: item.id,
        name: item.computer_name,
        kind: item.installation_kind,
      },
    ]),
  );
  for (const agent of agents.data?.agents ?? [])
    known.set(agent.device_id, {
      id: agent.device_id,
      name: agent.computer_name,
      kind: agent.installation_kind,
    });
  const targets = [...known.values()].sort((a, b) => a.name.localeCompare(b.name));
  const targetAgent = agents.data?.agents.find((item) => item.device_id === device);
  const ready = targetAgent?.online && targetAgent.protocol === 1;
  return (
    <PageBody className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Central de diagnóstico</h2>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void client.invalidateQueries({ queryKey: key })}
        >
          <RefreshCw />
          Atualizar
        </Button>
      </div>
      {(agents.isError || requests.isError) && (
        <p role="alert" className="text-sm text-destructive">
          {(agents.error ?? requests.error)?.message === "Not Found"
            ? "Reinicie a prévia para carregar a Central de diagnóstico no serviço local."
            : (agents.error ?? requests.error)?.message}
        </p>
      )}
      <Section title="Solicitar ao computador">
        <div className="diagnostic-request-form">
          <label>
            Computador
            <AppSelect
              label="Computador do diagnóstico"
              value={device}
              onValueChange={setDevice}
              placeholder="Selecione um computador"
              options={targets.map((item) => {
                const agent = agents.data?.agents.find((value) => value.device_id === item.id);
                const status = agents.isError
                  ? "Status indisponível"
                  : !agent || agent.protocol !== 1
                    ? "Atualizar cliente"
                    : agent.online
                      ? "Conectado"
                      : "Offline";
                const kind =
                  item.kind === "development"
                    ? "Prévia"
                    : item.kind === "installed"
                      ? "Instalado"
                      : "Versão não informada";
                return {
                  value: item.id,
                  label: `${item.name} · ${kind} · ${status}`,
                  disabled: !agent?.online || agent.protocol !== 1,
                };
              })}
            />
          </label>
          <label>
            Execuções
            <AppSelect
              label="Quantidade de execuções"
              value={String(maxRuns)}
              onValueChange={(value) => setMaxRuns(Number(value))}
              options={[5, 10, 20].map((value) => ({
                value: String(value),
                label: `Últimas ${value}`,
              }))}
            />
          </label>
          <label>
            Período
            <AppSelect
              label="Período do diagnóstico"
              value={String(days)}
              onValueChange={(value) => setDays(Number(value))}
              options={[
                { value: "1", label: "Último dia" },
                { value: "7", label: "Últimos 7 dias" },
                { value: "30", label: "Últimos 30 dias" },
              ]}
            />
          </label>
          <Button disabled={!ready || create.isPending} onClick={() => create.mutate()}>
            <Stethoscope />
            {create.isPending ? "Solicitando…" : "Solicitar diagnóstico"}
          </Button>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          O cliente precisa estar aberto e atualizado. A coleta verifica o ambiente e lê o
          histórico, sem executar o fluxo fiscal.
        </p>
      </Section>
      <TableBox maxH="max-h-[65vh]">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Computador</TableHead>
              <TableHead>Solicitado</TableHead>
              <TableHead>Situação</TableHead>
              <TableHead>Execuções com falha</TableHead>
              <TableHead>Verificações com atenção</TableHead>
              <TableHead>Solicitante</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(requests.data?.requests ?? []).map((item) => (
              <TableRow
                key={item.id}
                className="cursor-pointer"
                onClick={() => setSelected(item.id)}
              >
                <TableCell>
                  <Button
                    variant="link"
                    className="h-auto p-0"
                    onClick={() => setSelected(item.id)}
                  >
                    {item.computer_name}
                  </Button>
                </TableCell>
                <TableCell className="whitespace-nowrap text-xs">
                  {fmtDateTime(item.requested_at)}
                </TableCell>
                <TableCell>
                  <DiagnosticStatePill state={item.state} />
                </TableCell>
                <TableCell>{item.summary?.failed_runs ?? "—"}</TableCell>
                <TableCell>{item.summary?.issues ?? "—"}</TableCell>
                <TableCell className="text-xs">{item.requested_by}</TableCell>
              </TableRow>
            ))}
            {!requests.data?.requests.length && (
              <TableRow>
                <TableCell colSpan={6} className="py-12 text-center text-muted-foreground">
                  {requests.isLoading
                    ? "Carregando solicitações…"
                    : "Nenhum diagnóstico solicitado."}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableBox>
      <DiagnosticReportPanel
        key={selected ?? "closed"}
        open={!!selected}
        value={detail.data}
        error={detail.error?.message}
        onClose={() => setSelected(null)}
        onDownload={(value) => download.mutate(value)}
      />
    </PageBody>
  );
}
