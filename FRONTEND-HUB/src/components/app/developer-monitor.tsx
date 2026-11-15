import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Monitor,
  PackageCheck,
  RefreshCw,
  UsersRound,
} from "lucide-react";
import { useApi } from "@/services";
import { fmtDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageBody, Section } from "./page";
import { DeviceTable, SessionTable } from "./monitor-tables";
import { MonitorDetails } from "./monitor-details";
import { ClassificationFilters } from "./monitor-classification";
import { AppSelect } from "./fields/app-select";
import {
  classificationSearch,
  deviceClassification,
  type ClassifiedDevice,
} from "@/services/device-classification";

export function DeveloperMonitorPage() {
  const { api, mode, baseUrl } = useApi();
  const [search, setSearch] = useState("");
  const [connection, setConnection] = useState("all");
  const [installation, setInstallation] = useState("all");
  const [sector, setSector] = useState("all");
  const [branch, setBranch] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const developer = useQuery({
    queryKey: ["developer-config", mode, baseUrl],
    queryFn: () => api.getDeveloperConfig(),
    enabled: mode === "local",
    refetchInterval: 15000,
    retry: 0,
  });
  const allowed = mode === "local" && developer.data?.enabled;
  const query = useQuery({
    queryKey: ["developer-monitor", mode, baseUrl],
    queryFn: () => api.getDeveloperMonitor(),
    enabled: Boolean(allowed),
    refetchInterval: 15000,
    retry: 0,
  });
  if (!allowed)
    return (
      <PageBody>
        <Section title="Usuários e dispositivos">
          <p className="text-sm text-muted-foreground">
            {developer.isLoading
              ? "Verificando o modo desenvolvedor…"
              : "Este painel requer o modo desenvolvedor ativo neste computador."}
          </p>
        </Section>
      </PageBody>
    );
  const data = query.data;
  const normalize = (value: string) =>
    value
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("pt-BR");
  const normalized = normalize(search.trim());
  const matches = (values: string[]) =>
    !normalized || normalize(values.join(" ")).includes(normalized);
  const matchesClassification = (item: ClassifiedDevice) => {
    const value = deviceClassification(item);
    return (
      (sector === "all" || (value.sector?.code ?? "unknown") === sector) &&
      (branch === "all" || (value.branch?.code ?? "unknown") === branch)
    );
  };
  const matchesConnection = (online: boolean) =>
    connection === "all" || online === (connection === "online");
  const devices = (data?.devices ?? []).filter(
    (item) =>
      matchesConnection(item.online) &&
      matchesClassification(item) &&
      (installation === "all" || item.installation_kind === installation) &&
      matches([
        item.computer_name,
        item.windows_user,
        ...item.mac_addresses,
        ...item.operators,
        ...classificationSearch(item),
      ]),
  );
  const machineIds = new Set(
    (data?.devices ?? [])
      .filter((item) => installation === "all" || item.installation_kind === installation)
      .map((item) => item.machine_id),
  );
  const sessions = (data?.sessions ?? []).filter(
    (item) =>
      matchesConnection(item.online) &&
      matchesClassification(item) &&
      (installation === "all" || machineIds.has(item.machine_id)) &&
      matches([
        item.computer_name,
        item.windows_user,
        item.operator_name,
        ...item.mac_addresses,
        ...classificationSearch(item),
      ]),
  );
  return (
    <PageBody className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-3">
          <h2 className="text-xl font-semibold">Usuários e dispositivos</h2>
          <span className="text-xs text-muted-foreground">
            Atualizado {fmtDateTime(data?.checked_at)}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          <RefreshCw className={query.isFetching ? "animate-spin" : ""} />
          Atualizar painel
        </Button>
      </div>
      {query.isError && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive"
        >
          {(query.error as Error).message}
          {data && (
            <p className="mt-1">
              Os dados da última consulta permanecem visíveis até a conexão retornar.
            </p>
          )}
        </div>
      )}
      {data && (
        <>
          <dl className="grid grid-cols-2 divide-x divide-border rounded-lg border bg-card sm:grid-cols-3 xl:grid-cols-5">
            {(
              [
                ["Online", data.summary.online_devices, Monitor],
                ["Instalações", data.summary.detected_installations, PackageCheck],
                ["Conectados", data.summary.logged_in_users, UsersRound],
                ["Executando", data.summary.running_automations, Activity],
                ["Com falha", data.summary.broken_automations, AlertTriangle],
              ] as const
            ).map(([label, value, Icon]) => (
              <div key={label} className="px-5 py-4">
                <dt className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  {label}
                  <Icon className="h-3.5 w-3.5" />
                </dt>
                <dd className="mt-2 text-2xl font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <Section title="Computadores e sessões">
            <div className="mb-4 flex flex-wrap gap-3">
              <Input
                aria-label="Buscar usuários e dispositivos"
                className="min-w-52 flex-1"
                placeholder="Buscar operador, computador, setor ou filial…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <AppSelect
                label="Filtrar conexão"
                className="w-full sm:w-44"
                value={connection}
                onValueChange={setConnection}
                options={[
                  { value: "all", label: "Todas as conexões" },
                  { value: "online", label: "Online" },
                  { value: "offline", label: "Offline / sem sinal" },
                ]}
              />
              <AppSelect
                label="Filtrar instalação"
                className="w-full sm:w-48"
                value={installation}
                onValueChange={setInstallation}
                options={[
                  { value: "all", label: "Todas as instalações" },
                  { value: "installed", label: "Instalado" },
                  { value: "development", label: "Desenvolvimento" },
                  { value: "unreported", label: "Não informado" },
                ]}
              />
              <ClassificationFilters
                sector={sector}
                branch={branch}
                onSector={setSector}
                onBranch={setBranch}
              />
            </div>
            <Tabs defaultValue="devices">
              <TabsList className="mb-4">
                <TabsTrigger value="devices">Computadores ({devices.length})</TabsTrigger>
                <TabsTrigger value="sessions">Sessões ({sessions.length})</TabsTrigger>
              </TabsList>
              <TabsContent value="devices">
                <DeviceTable items={devices} onSelect={(device) => setSelected(device.id)} />
              </TabsContent>
              <TabsContent value="sessions">
                <SessionTable items={sessions} />
              </TabsContent>
            </Tabs>
            {data.local_pending_sync > 0 && (
              <p role="status" className="mt-2 text-xs text-warning-foreground">
                {data.local_pending_sync} registros aguardando sincronização.
              </p>
            )}
            {data.truncated && (
              <p role="status" className="mt-2 text-xs text-warning-foreground">
                O painel exibe até 1.000 registros de dispositivos e as 500 sessões mais recentes.
                Os indicadores se referem aos registros exibidos.
              </p>
            )}
          </Section>
          <MonitorDetails
            device={data.devices.find((item) => item.id === selected) ?? null}
            sessions={data.sessions}
            onClose={() => setSelected(null)}
          />
        </>
      )}
    </PageBody>
  );
}
