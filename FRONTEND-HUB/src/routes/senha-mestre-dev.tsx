import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, Save, ShieldCheck } from "lucide-react";
import { useApi } from "@/services";
import { PageBody, Section } from "@/components/app/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Pill } from "@/components/app/status";
import { fmtDateTime } from "@/lib/format";
import { toast } from "sonner";

export const Route = createFileRoute("/senha-mestre-dev")({
  head: () => ({ meta: [{ title: "Senha mestre · Cargo Hub" }] }),
  component: MasterPolicy,
});

export function MasterPolicy() {
  const { api, mode, baseUrl } = useApi();
  const client = useQueryClient();
  const developer = useQuery({
    queryKey: ["developer-config", mode, baseUrl],
    queryFn: () => api.getDeveloperConfig(),
    enabled: mode === "local",
    retry: 0,
    refetchInterval: 15000,
  });
  const allowed = mode === "local" && developer.data?.enabled === true;
  const key = ["master-policy", mode, baseUrl];
  const policy = useQuery({
    queryKey: key,
    queryFn: () => api.getMasterPolicy(),
    enabled: allowed,
    retry: 0,
    refetchInterval: 15000,
  });
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const save = useMutation({
    mutationFn: () => api.saveMasterPolicy(password),
    onSuccess: (value) => {
      setPassword("");
      setConfirmation("");
      setError("");
      client.setQueryData(key, value);
      client.removeQueries({ queryKey: ["config", mode, baseUrl] });
      client.removeQueries({ queryKey: ["health", mode, baseUrl] });
      void client.invalidateQueries({ queryKey: ["master-access"] });
      toast.success("Senha mestre salva.");
    },
    onError: (value: Error) => setError(value.message),
  });
  return (
    <PageBody className="max-w-3xl">
      <div className="flex items-center gap-3">
        <div className="rounded-xl bg-teal-500/10 p-3 text-teal-700">
          <KeyRound className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold">Senha mestre</h1>
          <p className="mt-1 text-sm text-muted-foreground">Única para todos os computadores.</p>
        </div>
      </div>
      {!allowed ? (
        <Section title="Acesso de desenvolvedor">
          <p className="text-sm text-muted-foreground">
            {developer.isPending && mode === "local"
              ? "Verificando acesso…"
              : developer.isError
                ? "Não foi possível verificar o acesso."
                : "Modo desenvolvedor desativado."}
          </p>
        </Section>
      ) : (
        <Section
          title={policy.data?.configured ? "Alterar senha mestre" : "Cadastrar senha mestre"}
          actions={
            <Pill tone={policy.data?.configured ? "success" : "warning"} icon={ShieldCheck}>
              {policy.data?.configured ? "Configurada" : "Não cadastrada"}
            </Pill>
          }
        >
          {policy.isPending ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : policy.isError ? (
            <p role="alert" className="text-sm text-destructive">
              {(policy.error as Error).message}
            </p>
          ) : (
            <form
              className="space-y-5"
              onSubmit={(event) => {
                event.preventDefault();
                if (password !== confirmation) {
                  setError("As senhas não coincidem.");
                  return;
                }
                if (password.length < 8) {
                  setError("Use pelo menos 8 caracteres.");
                  return;
                }
                setError("");
                save.mutate();
              }}
            >
              <div className="grid gap-5 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="policy-password">Nova senha mestre</Label>
                  <Input
                    id="policy-password"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    maxLength={256}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="policy-confirmation">Confirmar nova senha</Label>
                  <Input
                    id="policy-confirmation"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    maxLength={256}
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                  />
                </div>
              </div>
              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
              <div className="flex flex-wrap items-center justify-between gap-4 border-t pt-5">
                <p className="text-xs text-muted-foreground">
                  {policy.data?.updated_at
                    ? `Alterada em ${fmtDateTime(policy.data.updated_at)}`
                    : "Ainda não cadastrada"}
                </p>
                <Button disabled={!password || save.isPending} type="submit">
                  {save.isPending ? <Loader2 className="animate-spin" /> : <Save />}
                  {policy.data?.configured ? "Alterar senha mestre" : "Salvar senha mestre"}
                </Button>
              </div>
            </form>
          )}
        </Section>
      )}
    </PageBody>
  );
}
