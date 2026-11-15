import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Eye, EyeOff, Lock, Save, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageBody, Section } from "@/components/app/page";
import { Pill } from "@/components/app/status";
import { useApi, type ConfigGroup } from "@/services";
import { toast } from "sonner";
import { DeveloperSettings } from "@/components/app/developer-settings";
import { DesktopSettings } from "@/components/app/desktop-settings";
import { MasterAccessGate } from "@/components/app/master-access-gate";
import { UpdateButton } from "@/components/app/update-provider";

export const Route = createFileRoute("/configuracoes")({
  head: () => ({ meta: [
    { title: "Configurações e diagnóstico · Automação Novelis" },
    { name: "description", content: "Configure banco, documentos, automações e caminhos, e verifique a saúde do sistema." },
    { property: "og:title", content: "Configurações e diagnóstico · Automação Novelis" },
    { property: "og:description", content: "Configure banco, documentos, automações e caminhos, e verifique a saúde do sistema." },
  ] }),
  component: Config,
});

function Config() {
  return <MasterAccessGate><ConfigurationContent /></MasterAccessGate>;
}

function ConfigurationContent() {
  const { api, mode, baseUrl, setBaseUrl } = useApi();
  const health = useQuery({ queryKey: ["health", mode, baseUrl], queryFn: () => api.getHealth(), retry: 0 });
  const cfg = useQuery({ queryKey: ["config", mode, baseUrl], queryFn: () => api.getConfig(), retry: 0 });
  const [groups, setGroups] = useState<ConfigGroup[]>([]);
  const [show, setShow] = useState<Record<string, boolean>>({});
  const [url, setUrl] = useState(baseUrl);
  useEffect(() => { if (cfg.data) setGroups(cfg.data); }, [cfg.data]);
  useEffect(() => setUrl(baseUrl), [baseUrl]);
  const save = useMutation({ mutationFn: () => api.saveConfig(groups), onSuccess: () => toast.success("Configurações salvas"), onError: (e: Error) => toast.error(e.message) });
  const set = (gi: number, fi: number, v: string) => setGroups((g) => g.map((x, i) => (i !== gi ? x : { ...x, fields: x.fields.map((f, j) => (j === fi ? { ...f, value: v } : f)) })));
  return (
    <PageBody>
      <DesktopSettings />
      <Section title="Atualizações"><UpdateButton /></Section>
      <DeveloperSettings />
      <Section title="Conexão com o backend">
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1.5"><Label htmlFor="url">URL base da API</Label><Input id="url" className="w-80 font-mono" value={url} onChange={(e) => setUrl(e.target.value)} /></div>
          <Button variant="outline" onClick={() => { setBaseUrl(url); toast.success("URL atualizada"); }}>Aplicar</Button>
          <span className="text-xs text-muted-foreground">Modo atual: {mode === "demo" ? "Demonstração (dados fictícios)" : "Backend local"}</span>
        </div>
      </Section>
      <Section title="Diagnóstico das dependências" actions={<Button size="sm" variant="outline" onClick={() => health.refetch()}><RefreshCw className={health.isFetching ? "animate-spin" : ""} />Verificar</Button>}>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {(health.data ?? []).map((h) => (
            <div key={h.id} className="rounded-md border p-3"><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{h.nome}</span><Pill tone={h.status === "ok" ? "success" : h.status === "aviso" ? "warning" : "error"}>{h.status === "ok" ? "OK" : h.status === "aviso" ? "Atenção" : "Erro"}</Pill></div><div className="mt-1 text-xs text-muted-foreground">{h.grupo} · {h.detalhe}</div></div>
          ))}
          {health.isError && <p className="text-sm text-destructive">Diagnóstico indisponível: sem conexão com o backend.</p>}
        </div>
      </Section>
      <div className="grid gap-4 lg:grid-cols-2">
        {groups.map((g, gi) => (
          <Section key={g.id} title={g.titulo}>
            <div className="space-y-3">{g.fields.map((f, fi) => (
              <div key={f.key} className="space-y-1">
                <Label htmlFor={f.key} className="flex items-center gap-1">{f.sensitive && <Lock className="h-3 w-3" />}{f.label}{f.hint && <span className="font-normal text-muted-foreground">({f.hint})</span>}</Label>
                <div className="flex gap-1">
                  <Input id={f.key} className="font-mono text-sm" type={f.sensitive && !show[f.key] ? "password" : "text"} autoComplete="off" value={f.value} readOnly={f.readOnly} onChange={(e) => set(gi, fi, e.target.value)} />
                  {f.sensitive && <Button variant="outline" size="icon" aria-label={show[f.key] ? "Ocultar" : "Mostrar"} onClick={() => setShow((s) => ({ ...s, [f.key]: !s[f.key] }))}>{show[f.key] ? <EyeOff /> : <Eye />}</Button>}
                </div>
              </div>
            ))}</div>
          </Section>
        ))}
      </div>
      <div className="flex justify-end"><Button onClick={() => save.mutate()} disabled={save.isPending || !groups.length}><Save />Salvar configurações</Button></div>
    </PageBody>
  );
}
