import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Monitor,
  PackageCheck,
  RefreshCw,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { useApi } from "@/services";
import { fmtDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Kpi, PageBody, Section } from "./page";
import { DeviceTable, SessionTable } from "./monitor-tables";
import { MonitorDetails } from "./monitor-details";

export function DeveloperMonitorPage() {
  const { api, mode, baseUrl } = useApi();
  const [search, setSearch] = useState("");
  const [connection, setConnection] = useState("all");
  const [installation, setInstallation] = useState("all");
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
  const normalized = search.trim().toLocaleLowerCase("pt-BR");
  const matches = (values: string[]) =>
    !normalized || values.join(" ").toLocaleLowerCase("pt-BR").includes(normalized);
  const matchesConnection = (online: boolean) =>
    connection === "all" || online === (connection === "online");
  const devices = (data?.devices ?? []).filter(
    (item) =>
      matchesConnection(item.online) &&
      (installation === "all" || item.installation_kind === installation) &&
      matches([item.computer_name, item.windows_user, ...item.mac_addresses, ...item.operators]),
  );
  const machineIds = new Set(
    (data?.devices ?? [])
      .filter((item) => installation === "all" || item.installation_kind === installation)
      .map((item) => item.machine_id),
  );
  const sessions = (data?.sessions ?? []).filter(
    (item) =>
      matchesConnection(item.online) &&
      (installation === "all" || machineIds.has(item.machine_id)) &&
      matches([item.computer_name, item.windows_user, item.operator_name, ...item.mac_addresses]),
  );
  return (
    <PageBody className="space-y-5">
      <section className="relative overflow-hidden rounded-xl bg-primary p-5 text-primary-foreground lg:p-7">
        <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-teal-400/10" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-teal-300">
              <ShieldCheck className="h-4 w-4" />
              Console do desenvolvedor
            </div>
            <h2 className="text-2xl font-semibold tracking-tight">Usuários e dispositivos</h2>
            <p className="mt-2 max-w-2xl text-sm text-white/70">
              Acompanhe instalações detectadas, sessões dos operadores e o estado das automações.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            <RefreshCw className={query.isFetching ? "animate-spin" : ""} />
            Atualizar painel
          </Button>
        </div>
        <div className="relative mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/10 pt-4 text-xs text-white/65">
          <span className="inline-flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${query.isError ? "bg-amber-400" : data ? "bg-teal-400" : "bg-slate-400"}`}
            />
            {query.isError
              ? "Aguardando conexão"
              : data
                ? "Atualização a cada 15 segundos"
                : "Consultando registros…"}
          </span>
          <span>Dados recebidos: {fmtDateTime(data?.checked_at)}</span>
          <span>Fonte: registros compartilhados</span>
        </div>
      </section>
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
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Kpi
              label="Computadores online"
              value={data.summary.online_devices}
              icon={Monitor}
              tone="success"
              hint="Backend com sinal recente"
            />
            <Kpi
              label="Instalações detectadas"
              value={data.summary.detected_installations}
              icon={PackageCheck}
              tone="info"
              hint="Inclui computadores offline"
            />
            <Kpi
              label="Contas conectadas"
              value={data.summary.logged_in_users}
              icon={UsersRound}
              tone="success"
              hint="Sessões ativas com sinal"
            />
            <Kpi
              label="Em execução"
              value={data.summary.running_automations}
              icon={Activity}
              tone="info"
              hint="Automações online"
            />
            <Kpi
              label="Com falha"
              value={data.summary.broken_automations}
              icon={AlertTriangle}
              tone={data.summary.broken_automations ? "error" : "neutral"}
              hint="Último estado nos clientes online"
            />
          </div>
          <Section title="Acompanhamento dos clientes">
            <div className="mb-4 flex flex-wrap gap-3">
              <Input
                aria-label="Buscar usuários e dispositivos"
                className="min-w-52 flex-1"
                placeholder="Buscar operador, conta, computador ou MAC…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <select
                aria-label="Filtrar conexão"
                className="h-10 rounded-md border bg-background px-3 text-sm"
                value={connection}
                onChange={(event) => setConnection(event.target.value)}
              >
                <option value="all">Todas as conexões</option>
                <option value="online">Online</option>
                <option value="offline">Offline / sem sinal</option>
              </select>
              <select
                aria-label="Filtrar instalação"
                className="h-10 rounded-md border bg-background px-3 text-sm"
                value={installation}
                onChange={(event) => setInstallation(event.target.value)}
              >
                <option value="all">Todas as instalações</option>
                <option value="installed">Instalado</option>
                <option value="development">Desenvolvimento</option>
                <option value="unreported">Não informado</option>
              </select>
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
            <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
              O backend envia um sinal a cada 30 segundos, inclusive na bandeja. Após{" "}
              {data.online_timeout_seconds} segundos sem sinal, o cliente aparece offline. A
              instalação indica a última detecção; estar offline não confirma desinstalação. Sessão
              conectada indica atividade do aplicativo.
            </p>
            {data.local_pending_sync > 0 && (
              <p role="status" className="mt-2 text-xs text-amber-700">
                Este computador tem {data.local_pending_sync} registro(s) aguardando sincronização.
              </p>
            )}
            {data.truncated && (
              <p role="status" className="mt-2 text-xs text-amber-700">
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
