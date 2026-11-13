import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Save, ShieldOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageBody, Section, TableBox } from "@/components/app/page";
import { useApi, type AutomationStep } from "@/services";
import { toast } from "sonner";

export const Route = createFileRoute("/avancado")({
  head: () => ({ meta: [
    { title: "Área avançada · Automação Novelis" },
    { name: "description", content: "Passos, seletores, abas, timeouts e capturas da automação web." },
    { property: "og:title", content: "Área avançada · Automação Novelis" },
    { property: "og:description", content: "Passos, seletores, abas, timeouts e capturas da automação web." },
  ] }),
  component: Avancado,
});

function Avancado() {
  const { api, mode, baseUrl } = useApi();
  const q = useQuery({ queryKey: ["steps", mode, baseUrl], queryFn: () => api.listSteps(), retry: 0 });
  const [steps, setSteps] = useState<AutomationStep[]>([]);
  useEffect(() => { if (q.data) setSteps(q.data); }, [q.data]);
  const save = useMutation({ mutationFn: () => api.saveSteps(steps), onSuccess: () => toast.success("Passos salvos"), onError: (e: Error) => toast.error(e.message) });
  const upd = (i: number, p: Partial<AutomationStep>) => setSteps((s) => s.map((x, j) => (j === i ? { ...x, ...p } : x)));
  return (
    <PageBody>
      <div className="rounded-md border border-warning/50 bg-warning/15 p-3 text-sm text-warning-foreground">Alterações nesta área afetam diretamente a automação do portal Novelis. Edite apenas com orientação técnica.</div>
      {mode !== "demo" && <p className="text-sm text-muted-foreground">Consulta dos passos existentes. A edição utiliza o editor de pontos e passos da interface anterior.</p>}
      <Section title="Passos da automação (portal Novelis)" actions={<Button size="sm" onClick={() => save.mutate()} disabled={save.isPending || mode !== "demo"}><Save />Salvar</Button>}>
        <fieldset disabled={mode !== "demo"}>
        <TableBox>
          <Table className="min-w-[1000px]">
            <TableHeader><TableRow><TableHead>#</TableHead><TableHead>Passo</TableHead><TableHead>Ação</TableHead><TableHead>Ponto de interação (seletor)</TableHead><TableHead>Aba</TableHead><TableHead>Timeout (ms)</TableHead><TableHead>Captura</TableHead><TableHead>Ativo</TableHead></TableRow></TableHeader>
            <TableBody>{steps.map((s, i) => (
              <TableRow key={s.id}>
                <TableCell>{s.ordem}</TableCell><TableCell className="font-medium">{s.nome}</TableCell><TableCell>{s.acao}</TableCell>
                <TableCell><Input className="h-8 font-mono text-xs" value={s.seletor} onChange={(e) => upd(i, { seletor: e.target.value })} /></TableCell>
                <TableCell><Input className="h-8 w-28 text-xs" value={s.aba} onChange={(e) => upd(i, { aba: e.target.value })} /></TableCell>
                <TableCell><Input className="h-8 w-24 text-xs" type="number" value={s.timeoutMs} onChange={(e) => upd(i, { timeoutMs: Number(e.target.value) || 0 })} /></TableCell>
                <TableCell><Switch checked={s.captura} onCheckedChange={(v) => upd(i, { captura: v })} aria-label="Captura de tela" /></TableCell>
                <TableCell><Switch checked={s.ativo} onCheckedChange={(v) => upd(i, { ativo: v })} aria-label="Ativo" /></TableCell>
              </TableRow>
            ))}</TableBody>
          </Table>
        </TableBox>
        </fieldset>
      </Section>
      <Section title={<span className="flex items-center gap-2"><ShieldOff className="h-4 w-4" />Compatibilidade — fluxos antigos Rodopar</span>} className="opacity-60">
        <fieldset disabled className="space-y-2 text-sm">
          <p className="text-muted-foreground">Desativado. Mantido apenas para consulta dos fluxos legados de lançamento via Rodopar.</p>
          <div className="flex items-center gap-2"><Switch checked={false} /> Habilitar automação legada Rodopar</div>
        </fieldset>
      </Section>
    </PageBody>
  );
}
