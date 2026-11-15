import { createContext, useContext, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserRound, LogOut, Loader2, RefreshCw, ArrowRight } from "lucide-react";
import { useApi, type OperatorSession, type SessionState } from "@/services";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { BrandMark, BrandName } from "./brand";
import { DeviceCard } from "./device-card";
import { DeveloperCredit } from "./developer-credit";
import { desktop } from "@/services/desktop";
import { AppearanceMenu } from "./appearance-menu";

const SessionContext = createContext<{ session: OperatorSession | null; logout: () => void }>({
  session: null,
  logout: () => {},
});
export const useOperator = () => useContext(SessionContext);

export function SessionGate({ children }: { children: ReactNode }) {
  const { api, mode, baseUrl, setMode } = useApi();
  const qc = useQueryClient();
  const key = ["operator-session", mode, baseUrl];
  const query = useQuery({
    queryKey: key,
    queryFn: () => api.getSession(),
    enabled: mode === "local",
    refetchInterval: (value) =>
      value.state.status === "error" || !value.state.data
        ? 3000
        : value.state.data.session
          ? 15000
          : 8000,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: "always",
    networkMode: "always",
    retry: 0,
  });
  const nativeIdentity = useQuery({
    queryKey: ["native-device-identity"],
    queryFn: () => desktop.deviceIdentity(),
    enabled: mode === "local" && desktop.isDesktop,
    staleTime: Infinity,
    retry: 1,
  });
  const identity = query.data?.identity ?? nativeIdentity.data ?? undefined;
  const backendReady = Boolean(query.data?.identity) && !query.isError;
  const name = identity?.windows_user.split("\\").pop() || "";
  const login = useMutation({
    mutationFn: () => api.login(name.trim()),
    onSuccess: (data) => {
      qc.setQueryData(key, data);
      qc.invalidateQueries();
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const logout = useMutation({
    mutationFn: () => api.logout(),
    onSuccess: () => {
      qc.setQueryData<SessionState>(key, (previous) =>
        previous ? { ...previous, session: null } : undefined,
      );
      qc.invalidateQueries();
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const session = mode === "local" ? (query.data?.session ?? null) : null;
  if (mode === "demo" || session)
    return (
      <SessionContext.Provider value={{ session, logout: () => logout.mutate() }}>
        {query.data?.sync_error && (
          <div role="status" className="bg-warning/10 px-4 py-2 text-sm">
            Os registros de sessão estão preservados neste computador e aguardam sincronização com a
            pasta de logs.
          </div>
        )}
        {children}
      </SessionContext.Provider>
    );
  return (
    <div className="login-layout">
      <aside className="login-device-panel">
        <div className="relative flex items-center gap-3">
          <BrandMark tone="white" className="h-14 w-14" />
          <BrandName className="text-3xl" />
        </div>
        <DeviceCard identity={identity} />
      </aside>
      <main className="login-form-panel">
        <div className="absolute right-5 top-5">
          <AppearanceMenu />
        </div>
        <div className="w-full max-w-sm space-y-8">
          <div>
            <div className="mb-10 flex items-center gap-3 lg:hidden">
              <BrandMark className="h-12 w-12" />
              <BrandName className="text-2xl" />
            </div>
            <h2 className="text-3xl font-semibold tracking-tight text-primary">
              Entrar no Cargo Hub
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Entre com a conta Windows deste computador.
            </p>
          </div>
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              if (backendReady && name.trim().length >= 2 && !login.isPending) login.mutate();
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="operator-name">Nome do operador</Label>
              <Input
                id="operator-name"
                className="h-12 rounded-lg text-base"
                autoComplete="username"
                readOnly
                maxLength={100}
                value={name}
                placeholder="Identificando conta Windows…"
              />
            </div>
            <DeviceCard identity={identity} className="lg:hidden" />
            {!backendReady && (
              <div
                role="status"
                aria-live="polite"
                className="flex items-start gap-3 rounded-lg border border-primary/10 bg-primary/5 p-4 text-sm"
              >
                <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-teal-600" />
                <div>
                  <p className="font-medium">
                    {query.isError
                      ? query.isFetching
                        ? "Tentando conectar novamente…"
                        : "Aguardando o backend local"
                      : "Conectando ao Cargo Hub…"}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                    Reconexão automática.
                  </p>
                </div>
              </div>
            )}
            <Button
              className="h-12 w-full rounded-lg text-base"
              size="lg"
              type="submit"
              disabled={!backendReady || name.trim().length < 2 || login.isPending}
            >
              {login.isPending || !backendReady ? (
                <Loader2 className="animate-spin" />
              ) : (
                <UserRound />
              )}
              {backendReady ? "Entrar no Cargo Hub" : "Aguardando conexão…"}
              <ArrowRight className="ml-auto" />
            </Button>
          </form>
          <button
            className="text-sm text-muted-foreground underline-offset-4 hover:underline"
            onClick={() => setMode("demo")}
          >
            Abrir demonstração
          </button>
        </div>
        <DeveloperCredit />
      </main>
    </div>
  );
}

export function OperatorMenu() {
  const { session, logout } = useOperator();
  if (!session) return null;
  return (
    <div className="inline-flex items-center gap-2 border-l pl-2">
      <UserRound className="h-4 w-4" />
      <span
        className="max-w-32 truncate"
        title={`${session.windows_user} · ${session.computer_name}`}
      >
        {session.operator_name}
      </span>
      <Button size="sm" variant="ghost" onClick={logout} aria-label="Sair da sessão">
        <LogOut className="h-4 w-4" />
      </Button>
    </div>
  );
}
