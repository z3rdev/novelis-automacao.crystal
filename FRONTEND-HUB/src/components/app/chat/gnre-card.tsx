import { useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Upload, CheckCircle2, Clock3, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/services";
import { desktop } from "@/services/desktop";
import { chatStates, type GnreFileKind, type GnreRequest } from "@/services/chat";
import { Button } from "@/components/ui/button";
import { fmtDateTime } from "@/lib/format";

export function GnreCard({ value, room }: { value: GnreRequest; room: string }) {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const attempts = useRef(new Map<string, string>());
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["chat-room", mode, baseUrl, room] });
    void qc.invalidateQueries({ queryKey: ["chat-inbox", mode, baseUrl] });
    void qc.invalidateQueries({ queryKey: ["ctes"] });
  };
  const upload = useMutation({
    mutationFn: ({ kind, file }: { kind: GnreFileKind; file: File }) => {
      if (file.size > 20 * 1024 * 1024) throw new Error("Envie um arquivo com até 20 MB.");
      const key = `${kind}:${file.name}:${file.size}:${file.lastModified}`;
      const id = attempts.current.get(key) ?? crypto.randomUUID();
      attempts.current.set(key, id);
      return api.uploadGnre(room, value.id, kind, file, id);
    },
    onSuccess: (data) => {
      qc.setQueryData(["chat-room", mode, baseUrl, room, 0], data);
      refresh();
      toast.success("Documento registrado");
    },
    onError: (error: Error) => {
      refresh();
      toast.error(error.message);
    },
  });
  const claim = useMutation({
    mutationFn: () => api.claimGnre(room, value.id),
    onSuccess: refresh,
    onError: (error: Error) => toast.error(error.message),
  });
  const download = async (kind: GnreFileKind | "combined") => {
    try {
      const data = await api.downloadGnre(room, value.id, kind);
      await desktop.saveFile(
        `${kind === "combined" ? "GNRE-COMPROVANTE" : kind}_${value.cte}.pdf`,
        data,
      );
    } catch (error) {
      toast.error((error as Error).message);
    }
  };
  return (
    <article className="gnre-card" aria-label={`Documentos do CT-e ${value.cte}`}>
      <header>
        <strong>CT-e {value.cte}</strong>
        <span data-ready={["available", "archived"].includes(value.state)}>
          {chatStates[value.state]}
        </span>
      </header>
      {value.note && <p className="gnre-note">{value.note}</p>}
      <div className="gnre-documents">
        {(["guia", "comprovante"] as const).map((kind) => (
          <DocumentRow
            key={kind}
            kind={kind}
            value={value}
            busy={upload.isPending}
            onUpload={(file) => upload.mutate({ kind, file })}
            onDownload={() => void download(kind)}
          />
        ))}
      </div>
      <footer>
        <span>
          {value.assigned_name ? `Responsável · ${value.assigned_name}` : value.requested_name}
        </span>
        {!value.assigned_to && !["available", "archived", "expired"].includes(value.state) && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => claim.mutate()}
            disabled={claim.isPending}
          >
            Assumir
          </Button>
        )}
        {value.combined && ["available", "archived"].includes(value.state) && (
          <Button size="sm" variant="ghost" onClick={() => void download("combined")}>
            <Download />
            PDF unificado
          </Button>
        )}
        {value.chamado_url && (
          <Button
            size="icon"
            variant="ghost"
            aria-label="Abrir chamado Novelis"
            title={`Chamado ${value.chamado}`}
            onClick={() =>
              void desktop
                .openPath(value.chamado_url!)
                .catch(() => toast.error("Não foi possível abrir o chamado"))
            }
          >
            <ExternalLink />
          </Button>
        )}
      </footer>
    </article>
  );
}

function DocumentRow({
  kind,
  value,
  busy,
  onUpload,
  onDownload,
}: {
  kind: GnreFileKind;
  value: GnreRequest;
  busy: boolean;
  onUpload(file: File): void;
  onDownload(): void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const file = value[kind];
  const name = kind === "guia" ? "Guia GNRE" : "Comprovante de pagamento";
  return (
    <div className="gnre-document-row">
      {file ? (
        <CheckCircle2 className="text-success" />
      ) : (
        <Clock3 className="text-muted-foreground" />
      )}
      <div>
        <span>{name}</span>
        <small>
          {file
            ? `${file.uploaded_name ?? "Enviado"} · ${fmtDateTime(file.uploaded_at)}`
            : "Aguardando envio"}
        </small>
      </div>
      <input
        ref={input}
        className="sr-only"
        type="file"
        accept=".pdf,.png,.jpg,.jpeg"
        aria-label={`Arquivo de ${name}`}
        disabled={busy}
        onChange={(event) => {
          const selected = event.currentTarget.files?.[0];
          if (selected) onUpload(selected);
          event.currentTarget.value = "";
        }}
      />
      {file && value.state !== "expired" && (
        <Button variant="ghost" size="icon" aria-label={`Baixar ${name}`} onClick={onDownload}>
          <Download />
        </Button>
      )}
      <Button variant="outline" size="sm" onClick={() => input.current?.click()} disabled={busy}>
        <Upload />
        {busy ? "Enviando…" : file ? "Substituir" : "Enviar"}
      </Button>
    </div>
  );
}
