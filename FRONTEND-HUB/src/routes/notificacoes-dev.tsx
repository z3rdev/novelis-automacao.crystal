import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Archive, Send, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useApi, type NotificationInput } from "@/services";
import { PageBody, Section } from "@/components/app/page";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { noticeLevels } from "@/components/app/notification-dialog";
import { fmtDateTime } from "@/lib/format";
import { AppSelect } from "@/components/app/fields/app-select";
import { AppDateTimePicker } from "@/components/app/fields/app-date-time-picker";

export const Route = createFileRoute("/notificacoes-dev")({
  head: () => ({ meta: [{ title: "Central de notificações · Cargo Hub" }] }),
  component: DeveloperNotifications,
});

function DeveloperNotifications() {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [severity, setSeverity] = useState<NotificationInput["severity"]>("info");
  const [expires, setExpires] = useState("");
  const developer = useQuery({
    queryKey: ["developer-config", mode, baseUrl],
    queryFn: () => api.getDeveloperConfig(),
    enabled: mode === "local",
    refetchInterval: 15000,
    retry: 0,
  });
  const allowed = mode === "local" && developer.data?.enabled;
  const feed = useQuery({
    queryKey: ["developer-notifications", mode, baseUrl],
    queryFn: () => api.getDeveloperNotifications(),
    enabled: Boolean(allowed),
    refetchInterval: 20000,
    retry: 0,
  });
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["developer-notifications"] });
    void qc.invalidateQueries({ queryKey: ["notifications"] });
  };
  const publish = useMutation({
    mutationFn: () =>
      api.publishNotification({
        title: title.trim(),
        body: body.trim(),
        severity,
        expires_at: expires ? new Date(expires).toISOString() : null,
      }),
    onSuccess: () => {
      setTitle("");
      setBody("");
      setExpires("");
      refresh();
      toast.success("Notificação publicada para os operadores.");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const archive = useMutation({
    mutationFn: (id: string) => api.archiveNotification(id),
    onSuccess: () => {
      refresh();
      toast.success("Aviso encerrado.");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  if (!allowed)
    return (
      <PageBody>
        <Section title="Central de notificações">
          <p className="text-sm text-muted-foreground">
            {developer.isLoading
              ? "Verificando o modo desenvolvedor…"
              : "Esta tela requer o modo desenvolvedor ativo neste computador."}
          </p>
        </Section>
      </PageBody>
    );
  return (
    <PageBody>
      <Section title="Publicar notificação">
        <p className="mb-5 text-sm text-muted-foreground">
          O comunicado será publicado no servidor do Cargo Hub e disponibilizado aos operadores.
        </p>
        <form
          className="max-w-3xl space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            publish.mutate();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="notice-title">Título</Label>
            <Input
              id="notice-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={160}
              minLength={3}
              required
              placeholder="Título do comunicado"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="notice-body">Mensagem</Label>
            <Textarea
              id="notice-body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              maxLength={10000}
              rows={6}
              required
              placeholder="Escreva a mensagem para os operadores"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="notice-severity">Prioridade</Label>
              <AppSelect
                label="Prioridade"
                id="notice-severity"
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                value={severity}
                onValueChange={(value) => setSeverity(value as NotificationInput["severity"])}
                options={Object.entries(noticeLevels).map(([value, label]) => ({ value, label }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="notice-expires">Expiração opcional</Label>
              <AppDateTimePicker
                label="Expiração opcional"
                id="notice-expires"
                value={expires}
                onChange={setExpires}
              />
            </div>
          </div>
          <Button
            type="submit"
            disabled={publish.isPending || title.trim().length < 3 || !body.trim()}
          >
            {publish.isPending ? <Loader2 className="animate-spin" /> : <Send />}Publicar
            notificação
          </Button>
        </form>
      </Section>
      <Section title="Notificações publicadas">
        {feed.isError && (
          <p role="alert" className="text-sm text-destructive">
            Não foi possível consultar o servidor de notificações.
          </p>
        )}
        {feed.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">Nenhuma notificação publicada.</p>
        )}
        <div className="divide-y">
          {(feed.data ?? []).map((item) => {
            const expired = item.expires_at && new Date(item.expires_at).getTime() <= Date.now();
            const inactive = item.archived_at || expired;
            return (
              <article
                key={item.id}
                className="flex flex-wrap items-start justify-between gap-4 py-4 first:pt-0"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-muted-foreground">
                    {noticeLevels[item.severity]} · {fmtDateTime(item.created_at)} · {item.author}
                  </p>
                  <h3 className="mt-1 break-words font-medium">{item.title}</h3>
                  <p className="mt-2 whitespace-pre-wrap break-words text-sm text-muted-foreground">
                    {item.body}
                  </p>
                  {inactive && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      {item.archived_at ? "Encerrada" : "Expirada"}
                    </p>
                  )}
                </div>
                {!inactive && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => archive.mutate(item.id)}
                    disabled={archive.isPending}
                  >
                    <Archive />
                    Encerrar aviso
                  </Button>
                )}
              </article>
            );
          })}
        </div>
      </Section>
    </PageBody>
  );
}
