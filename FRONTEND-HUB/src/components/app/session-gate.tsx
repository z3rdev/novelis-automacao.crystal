import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
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
    refetchInterval: 15000,
    retry: 0,
  });
  const [name, setName] = useState("");
  useEffect(() => {
    if (query.data?.identity.windows_user)
      setName((previous) => previous || query.data.identity.windows_user.split("\\").pop() || "");
  }, [query.data?.identity.windows_user]);
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
  const identity = query.data?.identity;
  return (
    <div className="login-layout">
      <aside className="login-device-panel">
        <div className="relative flex items-center gap-3"><BrandMark tone="white" className="h-14 w-14" /><BrandName className="text-3xl" /></div>
        <DeviceCard identity={identity} />
      </aside>
      <main className="login-form-panel">
        <div className="w-full max-w-sm space-y-8">
          <div>
            <div className="mb-10 flex items-center gap-3 lg:hidden">
              <BrandMark className="h-12 w-12" /><BrandName className="text-2xl" />
            </div>
            <h2 className="text-3xl font-semibold tracking-tight text-primary">Entrar no Cargo Hub</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Informe seu nome para identificar esta sessão de trabalho.
            </p>
          </div>
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              login.mutate();
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="operator-name">Nome do operador</Label>
              <Input
                id="operator-name"
                className="h-12 rounded-lg text-base"
                autoComplete="name"
                autoFocus
                maxLength={100}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Seu nome"
              />
            </div>
            <DeviceCard identity={identity} className="lg:hidden" />
            {query.isError && (
              <div role="alert" className="space-y-3 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
                <p>{(query.error as Error).message}</p>
                <Button variant="outline" size="sm" type="button" onClick={() => query.refetch()} disabled={query.isFetching}><RefreshCw className={query.isFetching ? "animate-spin" : ""} />Tentar novamente</Button>
              </div>
            )}
            <Button
              className="h-12 w-full rounded-lg text-base"
              size="lg"
              type="submit"
              disabled={!identity || name.trim().length < 2 || login.isPending}
            >
              {login.isPending ? <Loader2 className="animate-spin" /> : <UserRound />}
              Entrar no Cargo Hub<ArrowRight className="ml-auto" />
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
