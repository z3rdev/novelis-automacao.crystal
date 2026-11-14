import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, FolderOpen, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/services";
import { desktop } from "@/services/desktop";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";

export function ReleasePublisher() {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const key = ["release-publish", mode, baseUrl];
  const [path, setPath] = useState("");
  const [version, setVersion] = useState("");
  const [notes, setNotes] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const previousStatus = useRef("");
  const status = useQuery({
    queryKey: key,
    queryFn: () => api.getPublishStatus(),
    retry: 0,
    refetchInterval: (query) =>
      ["validating", "uploading", "publishing"].includes(query.state.data?.status ?? "")
        ? 1000
        : 15000,
  });
  const publish = useMutation({
    mutationFn: () =>
      api.publishRelease({
        installer_path: path,
        version: version.trim(),
        notes: notes.trim(),
        distribution_authorized: authorized,
      }),
    onSuccess: (data) => qc.setQueryData(key, data),
    onError: (error: Error) => toast.error(error.message),
  });
  useEffect(() => {
    if (
      status.data?.status === "published" &&
      previousStatus.current &&
      previousStatus.current !== "published"
    ) {
      toast.success(status.data.message);
      void api
        .checkUpdates()
        .then(() => qc.invalidateQueries({ queryKey: ["updates", mode, baseUrl] }))
        .catch(() => {});
    }
    previousStatus.current = status.data?.status ?? "";
  }, [status.data?.status, status.data?.message, api, qc, mode, baseUrl]);
  const busy =
    publish.isPending ||
    ["validating", "uploading", "publishing"].includes(status.data?.status ?? "");
  const progress = status.data?.total_bytes
    ? Math.min(100, Math.round((status.data.sent_bytes / status.data.total_bytes) * 100))
    : 0;
  const pick = async () => {
    try {
      const selected = await desktop.pickInstaller();
      if (!selected) return;
      setPath(selected);
      setAuthorized(false);
      const name = selected.split(/[\\/]/).pop() ?? "";
      const detected = /^NovelisCargoHubSetup-(\d+\.\d+\.\d+(?:-r[1-9]\d*)?)(?:-|\.exe$)/.exec(
        name,
      );
      setVersion(detected?.[1] ?? "");
    } catch {
      toast.error("Não foi possível selecionar o instalador.");
    }
  };
  return (
    <form
      className="mt-6 space-y-4 border-t pt-5"
      onSubmit={(event) => {
        event.preventDefault();
        publish.mutate();
      }}
    >
      <h3 className="text-sm font-semibold">Publicar atualização</h3>
      <div className="space-y-1.5">
        <Label htmlFor="release-installer">Instalador Cargo Hub</Label>
        <div className="flex gap-2">
          <Input
            id="release-installer"
            readOnly
            value={path}
            placeholder="Selecione o pacote .exe"
            className="min-w-0 font-mono text-xs"
          />
          <Button type="button" variant="outline" onClick={() => void pick()} disabled={busy}>
            <FolderOpen />
            Selecionar
          </Button>
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="release-version">Versão</Label>
        <Input
          id="release-version"
          value={version}
          onChange={(event) => {
            setVersion(event.target.value);
            setAuthorized(false);
          }}
          placeholder="0.1.35 ou 0.1.34-r9"
          disabled={busy}
          className="max-w-xs font-mono"
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="release-notes">Notas da atualização</Label>
        <Textarea
          id="release-notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Descreva as alterações desta versão"
          maxLength={10000}
          disabled={busy}
          required
        />
      </div>
      <div className="flex items-start gap-2">
        <Checkbox
          id="release-authorized"
          checked={authorized}
          onCheckedChange={(value) => setAuthorized(value === true)}
          disabled={busy}
        />
        <Label htmlFor="release-authorized" className="text-xs font-normal leading-relaxed">
          Confirmo que este pacote está autorizado para publicação e distribuição, incluindo os
          componentes e configurações incorporados.
        </Label>
      </div>
      <Button
        type="submit"
        disabled={busy || !path || !version.trim() || !notes.trim() || !authorized}
      >
        {busy ? <Loader2 className="animate-spin" /> : <FileUp />}
        {busy ? "Publicando…" : "Publicar atualização"}
      </Button>
      {status.data && status.data.status !== "idle" && (
        <div className="space-y-2" aria-live="polite">
          <p
            role={status.data.status === "error" ? "alert" : "status"}
            className={
              status.data.status === "error"
                ? "text-sm text-destructive"
                : "text-sm text-muted-foreground"
            }
          >
            {status.data.message}
          </p>
          {["uploading", "publishing"].includes(status.data.status) && (
            <>
              <Progress value={progress} aria-label="Envio do instalador" />
              <p className="text-xs text-muted-foreground">{progress}% enviado</p>
            </>
          )}
          {status.data.status === "published" && (
            <p className="break-all font-mono text-xs">
              {status.data.filename} · {status.data.version}
            </p>
          )}
        </div>
      )}
      {status.isError && (
        <p role="alert" className="text-sm text-destructive">
          Não foi possível consultar a publicação no backend.
        </p>
      )}
    </form>
  );
}
