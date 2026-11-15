import { useEffect, useState, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LockKeyhole, ShieldCheck, KeyRound, Loader2 } from "lucide-react";
import { useApi, type MasterAccessState } from "@/services";
import { useOperator } from "./session-gate";
import { PageBody } from "./page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function MasterAccessGate({ children }: { children: ReactNode }) {
  const { api, mode, baseUrl } = useApi();
  const { session } = useOperator();
  const client = useQueryClient();
  const key = ["master-access", mode, baseUrl, session?.id];
  const state = useQuery({
    queryKey: key,
    queryFn: () => api.getMasterAccess(),
    enabled: mode === "local",
    retry: 0,
    staleTime: 0,
    refetchOnWindowFocus: "always",
    refetchInterval: 5000,
  });
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const unlock = useMutation({
    mutationFn: () => api.unlockMasterAccess(password),
    onSuccess: (value) => {
      setPassword("");
      setError("");
      client.setQueryData(key, value);
    },
    onError: (value: Error) => {
      setError(value.message);
      void state.refetch();
    },
  });
  const lock = useMutation({
    mutationFn: () => api.lockMasterAccess(),
    onSuccess: () => {
      client.setQueryData<MasterAccessState>(
        key,
        (value) => value && { ...value, unlocked: false, expires_at: null },
      );
    },
    onError: (value: Error) => setError(value.message),
  });
  useEffect(() => {
    if (!state.data?.unlocked) {
      client.removeQueries({ queryKey: ["config", mode, baseUrl] });
      client.removeQueries({ queryKey: ["health", mode, baseUrl] });
    }
  }, [state.data?.unlocked, client, mode, baseUrl]);
  if (state.data?.unlocked && !state.isError)
    return (
      <>
        <div className="flex items-center justify-end gap-3 border-b bg-teal-500/5 px-6 py-1 text-xs">
          <ShieldCheck className="h-4 w-4 text-teal-700" />
          <Button size="sm" variant="ghost" disabled={lock.isPending} onClick={() => lock.mutate()}>
            <LockKeyhole />
            Bloquear
          </Button>
        </div>
        {children}
      </>
    );
  return (
    <PageBody className="flex min-h-[75vh] max-w-5xl items-center justify-center">
      <section className="w-full max-w-md overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div className="bg-primary p-7 text-white">
          <LockKeyhole className="mb-4 h-8 w-8 text-teal-300" />
          <h2 className="text-2xl font-semibold">Configurações protegidas</h2>
        </div>
        <div className="p-7">
          {state.isPending && mode === "local" ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Verificando acesso…
            </p>
          ) : mode !== "local" ? (
            <p className="text-sm text-muted-foreground">Conecte ao backend local.</p>
          ) : state.isError ? (
            <p role="status" className="text-sm text-muted-foreground">
              Sem conexão. Tentando novamente…
            </p>
          ) : !state.data?.configured ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">Senha mestre não cadastrada.</p>
              {state.data?.can_setup && (
                <Button asChild>
                  <Link to="/senha-mestre-dev">
                    <KeyRound />
                    Gerenciar senha mestre
                  </Link>
                </Button>
              )}
            </div>
          ) : (
            <form
              className="space-y-5"
              onSubmit={(event) => {
                event.preventDefault();
                setError("");
                unlock.mutate();
              }}
            >
              <div className="space-y-2">
                <Label htmlFor="master-password">Senha mestre</Label>
                <Input
                  id="master-password"
                  type="password"
                  autoComplete="current-password"
                  maxLength={256}
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="h-11"
                />
              </div>
              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
              <Button className="h-11 w-full" disabled={unlock.isPending || !password}>
                <KeyRound />
                Desbloquear configurações
                {unlock.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              </Button>
            </form>
          )}
        </div>
      </section>
    </PageBody>
  );
}
