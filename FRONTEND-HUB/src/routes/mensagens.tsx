import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { MessageSquareText, Save } from "lucide-react";
import { useApi, type MessageConfiguration } from "@/services";
import { PageBody, Section } from "@/components/app/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export const Route = createFileRoute("/mensagens")({
  component: Messages,
  head: () => ({ meta: [{ title: "Modelo do chamado · Cargo Hub" }] }),
});
const samples: Record<string, string> = {
  cte: "2-10-12345",
  percurso: "Exemplo",
  ton: "25",
  id: "123",
  idTarifario: "456",
  rota: "Origem x Destino",
  cteOrigem: "2-10-12340",
  chamadoOrigem: "987654",
  assinatura: "",
};
export function messagePreview(template: string, signature: string) {
  return template.replace(/\{([A-Za-z]+)\}/g, (whole, key: string) =>
    key === "assinatura" ? signature : (samples[key] ?? whole),
  );
}

function Messages() {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const key = ["message-configuration", mode, baseUrl];
  const query = useQuery({ queryKey: key, queryFn: () => api.getMessages(), retry: 0 });
  const [draft, setDraft] = useState<MessageConfiguration | null>(null);
  const [complement, setComplement] = useState(false);
  useEffect(() => {
    if (query.data) setDraft(query.data);
  }, [query.data]);
  const save = useMutation({
    mutationFn: () => api.saveMessages(draft!),
    onSuccess: (value) => {
      qc.setQueryData(key, value);
      void qc.invalidateQueries({ queryKey: ["ctes"] });
      toast.success("Modelo e permissão salvos.");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const patch = (values: Partial<MessageConfiguration>) =>
    setDraft((previous) => previous && { ...previous, ...values });
  return (
    <PageBody>
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <MessageSquareText />
          Modelo do chamado
        </h1>
      </div>
      {query.isError && (
        <p role="alert" className="text-sm text-destructive">
          {(query.error as Error).message}
        </p>
      )}
      {draft && (
        <>
          <Section title="Regra de documentos">
            <div className="flex items-start gap-3">
              <Switch
                id="allow-receipt"
                checked={draft.allow_missing_receipt}
                onCheckedChange={(value) => patch({ allow_missing_receipt: value })}
              />
              <div>
                <Label htmlFor="allow-receipt">Permitir abertura de chamado sem comprovante</Label>
              </div>
            </div>
          </Section>
          <div className="grid items-start gap-4 xl:grid-cols-2">
            <Section title="Conteúdo da mensagem">
              <div className="space-y-4">
                <div className="space-y-1">
                  <Label htmlFor="message-title">Título</Label>
                  <Input
                    id="message-title"
                    value={draft.title}
                    maxLength={160}
                    onChange={(event) => patch({ title: event.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="message-signature">Assinatura</Label>
                  <Textarea
                    id="message-signature"
                    rows={2}
                    maxLength={1000}
                    value={draft.signature}
                    onChange={(event) => patch({ signature: event.target.value })}
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant={!complement ? "default" : "outline"}
                    onClick={() => setComplement(false)}
                  >
                    CT-e normal
                  </Button>
                  <Button
                    variant={complement ? "default" : "outline"}
                    onClick={() => setComplement(true)}
                  >
                    CT-e complementar
                  </Button>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="message-body">
                    Mensagem {complement ? "complementar" : "normal"}
                  </Label>
                  <Textarea
                    id="message-body"
                    rows={15}
                    className="font-mono text-xs"
                    maxLength={10000}
                    value={complement ? draft.complement_message : draft.message}
                    onChange={(event) =>
                      patch(
                        complement
                          ? { complement_message: event.target.value }
                          : { message: event.target.value },
                      )
                    }
                  />
                </div>
                <details className="text-xs text-muted-foreground">
                  <summary className="cursor-pointer">Variáveis disponíveis</summary>
                  <p className="mt-2 font-mono leading-6">
                    {Object.keys(samples)
                      .map((name) => `{${name}}`)
                      .join(" · ")}
                  </p>
                </details>
              </div>
            </Section>
            <Section title="Prévia com dados de exemplo">
              <h2 className="mb-4 font-semibold">{messagePreview(draft.title, draft.signature)}</h2>
              <div className="whitespace-pre-wrap break-words rounded-lg bg-muted/50 p-4 text-sm leading-relaxed">
                {messagePreview(
                  complement ? draft.complement_message : draft.message,
                  draft.signature,
                )}
              </div>
            </Section>
          </div>
          <div className="flex justify-end">
            <Button disabled={save.isPending || mode !== "local"} onClick={() => save.mutate()}>
              <Save />
              Salvar modelo e permissão
            </Button>
          </div>
        </>
      )}
    </PageBody>
  );
}
