import { Download, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import type { UpdateStatus } from "@/services";

interface Props {
  open: boolean;
  onOpenChange(open: boolean): void;
  data: UpdateStatus | undefined;
  checking: boolean;
  busy: boolean;
  automationRunning: boolean;
  onCheck(): void;
  onDownload(): void;
  onInstall(): void;
}

const megabytes = (bytes: number) =>
  `${(bytes / 1024 ** 2).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;

export function UpdateDialog({
  open,
  onOpenChange,
  data,
  checking,
  busy,
  automationRunning,
  onCheck,
  onDownload,
  onInstall,
}: Props) {
  const release = data?.release;
  const downloading = data?.status === "downloading";
  const ready = data?.status === "ready";
  const installing = data?.status === "installing";
  const percent = release
    ? Math.min(100, Math.round((data.received_bytes / release.size) * 100))
    : 0;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto rounded-xl">
        <DialogHeader>
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-accent text-accent-foreground">
            <Download className="h-6 w-6" />
          </div>
          <DialogTitle>{release ? release.title : "Atualizações do Cargo Hub"}</DialogTitle>
          <DialogDescription>
            {data?.current_version
              ? `Versão atual ${data.current_version}`
              : "Verifique as versões disponíveis para este computador."}
          </DialogDescription>
        </DialogHeader>
        {release && (
          <>
            <div className="flex items-center justify-between rounded-lg border bg-muted/40 p-4">
              <div>
                <p className="text-xs text-muted-foreground">Nova versão</p>
                <p className="text-xl font-semibold text-primary">{release.version}</p>
              </div>
              <span className="text-sm text-muted-foreground">
                Windows x64 · {megabytes(release.size)}
              </span>
            </div>
            {release.notes && (
              <div className="max-h-52 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed">
                {release.notes}
              </div>
            )}
          </>
        )}
        {checking ? (
          <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Consultando o servidor de releases…
          </p>
        ) : (
          <p
            role={data?.status === "error" ? "alert" : "status"}
            className={
              data?.status === "error"
                ? "text-sm text-destructive"
                : "text-sm text-muted-foreground"
            }
          >
            {data?.message || "Verifique se há uma atualização disponível."}
          </p>
        )}
        {downloading && (
          <div className="space-y-2">
            <Progress value={percent} aria-label="Download da atualização" />
            <p className="text-xs text-muted-foreground">
              {percent}% · {megabytes(data.received_bytes)} de {megabytes(release?.size ?? 0)}
            </p>
          </div>
        )}
        {ready && (
          <p className="text-xs text-muted-foreground">
            A atualização abrirá o instalador, que encerrará o aplicativo para substituir os
            arquivos.
          </p>
        )}
        {ready && !data.can_install && (
          <p className="text-xs text-muted-foreground">
            A instalação fica disponível na cópia instalada do Cargo Hub.
          </p>
        )}
        {ready && automationRunning && (
          <p className="text-sm text-warning">Aguarde a automação encerrar para instalar.</p>
        )}
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Agora não
          </Button>
          {!downloading && !installing && !ready && data?.status !== "available" && (
            <Button onClick={onCheck} disabled={checking || busy}>
              <RefreshCw className={checking ? "animate-spin" : ""} />
              Verificar novamente
            </Button>
          )}
          {data?.status === "available" && (
            <Button onClick={onDownload} disabled={busy}>
              <Download />
              Baixar atualização
            </Button>
          )}
          {ready && (
            <Button onClick={onInstall} disabled={busy || !data.can_install || automationRunning}>
              Instalar atualização
            </Button>
          )}
          {(downloading || installing) && (
            <Button disabled>
              <Loader2 className="animate-spin" />
              {downloading ? "Baixando…" : "Abrindo instalador…"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
