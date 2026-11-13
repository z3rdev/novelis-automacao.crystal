import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Monitor, UserRound, Truck, LogOut, Loader2 } from "lucide-react";
import { useApi, type OperatorSession, type SessionState } from "@/services";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

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
    <div className="grid min-h-screen w-full bg-background lg:grid-cols-[minmax(320px,0.9fr)_minmax(480px,1.1fr)]">
      <aside className="hidden flex-col justify-between bg-sidebar p-12 text-sidebar-foreground lg:flex">
        <div className="flex items-center gap-3">
          <Truck className="h-9 w-9" />
          <span className="text-xl font-semibold">Novelis Cargo Hub</span>
        </div>
        <div className="space-y-5">
          <h1 className="max-w-sm break-all text-4xl font-semibold leading-tight">
            {identity?.computer_name ?? "Dispositivo local"}
          </h1>
          <div className="border-t border-sidebar-border pt-5 text-sm">
            <p className="text-sidebar-foreground/65">Conta Windows</p>
            <p className="mt-1 break-all font-mono">{identity?.windows_user ?? "Identificando…"}</p>
          </div>
        </div>
        <p className="text-sm text-sidebar-foreground/60">
          Registro de acesso e execução por operador e dispositivo.
        </p>
      </aside>
      <main className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md space-y-8">
          <div>
            <div className="mb-8 flex items-center gap-2 text-primary lg:hidden">
              <Truck />
              Novelis Cargo Hub
            </div>
            <h2 className="text-3xl font-semibold tracking-tight">Entrar</h2>
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
                autoComplete="name"
                autoFocus
                maxLength={100}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Seu nome"
              />
            </div>
            <div className="rounded-lg border bg-card p-4 text-sm">
              <div className="mb-3 flex items-center gap-2 font-medium">
                <Monitor className="h-4 w-4" />
                {identity?.computer_name ?? "Identificando dispositivo…"}
              </div>
              <p className="break-all text-muted-foreground">{identity?.windows_user}</p>
              <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                MAC {identity?.mac_addresses.join(" · ") || "não disponível"}
              </p>
            </div>
            {query.isError && (
              <p role="alert" className="text-sm text-destructive">
                Não foi possível conectar ao backend. {(query.error as Error).message}
              </p>
            )}
            <Button
              className="w-full"
              size="lg"
              type="submit"
              disabled={!identity || name.trim().length < 2 || login.isPending}
            >
              {login.isPending ? <Loader2 className="animate-spin" /> : <UserRound />}Entrar no
              Cargo Hub
            </Button>
          </form>
          <button
            className="text-sm text-muted-foreground underline-offset-4 hover:underline"
            onClick={() => setMode("demo")}
          >
            Abrir demonstração
          </button>
        </div>
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
