import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useApi } from "@/services";
import type { ChatDirectory } from "@/services/chat";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { AppSelect } from "../fields/app-select";
import { GnrePendingSelect } from "./gnre-pending-select";

export function ChatDialog({
  open,
  close,
  directory,
  initialCte = "",
  gnre,
  selectedRoom,
  onCreated,
}: {
  open: boolean;
  close(): void;
  directory: ChatDirectory | undefined;
  initialCte?: string;
  gnre: boolean;
  selectedRoom?: string;
  onCreated(id: string): void;
}) {
  const { api } = useApi();
  const qc = useQueryClient();
  const [type, setType] = useState<"sector" | "operator">("sector");
  const [target, setTarget] = useState("FIN");
  const [cte, setCte] = useState(initialCte);
  const [note, setNote] = useState("");
  const [chamado, setChamado] = useState("");
  const attempt = useRef<{ key: string; id: string } | null>(null);
  const operators = (directory?.operators ?? []).filter(
    (item) => item.online && item.sector === "FIN",
  );
  const recipientAvailable =
    type === "sector" ? target === "FIN" : operators.some((item) => item.key === target);
  const save = useMutation({
    mutationFn: async () => {
      const room = selectedRoom ?? (await api.createChatRoom(type, target)).id;
      if (gnre) {
        const key = JSON.stringify([room, cte.trim(), note.trim(), chamado.trim()]);
        if (attempt.current?.key !== key) attempt.current = { key, id: crypto.randomUUID() };
        await api.requestGnre(room, {
          cte: cte.trim(),
          note: note.trim(),
          chamado: chamado.trim(),
          client_id: attempt.current.id,
        });
      }
      return room;
    },
    onSuccess: (room) => {
      attempt.current = null;
      void qc.invalidateQueries({ queryKey: ["chat-inbox"] });
      void qc.invalidateQueries({ queryKey: ["chat-room"] });
      onCreated(room);
      close();
    },
    onError: (error: Error) => toast.error(error.message),
  });
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value && !save.isPending) close();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{gnre ? "Solicitar guia e comprovante" : "Nova conversa"}</DialogTitle>
          <DialogDescription>
            {selectedRoom ? "Enviar nesta conversa." : "Escolha um setor ou operador."}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if ((selectedRoom || recipientAvailable) && !save.isPending) save.mutate();
          }}
        >
          {!selectedRoom && (
            <>
              <AppSelect
                label="Tipo de destinatário"
                value={type}
                onValueChange={(value) => {
                  const next = value as "operator" | "sector";
                  setType(next);
                  setTarget(next === "sector" ? "FIN" : "");
                }}
                options={[
                  { value: "sector", label: "Setor" },
                  { value: "operator", label: "Operador" },
                ]}
              />
              <AppSelect
                label="Destinatário"
                value={target}
                onValueChange={setTarget}
                placeholder={
                  type === "operator" && !operators.length
                    ? "Nenhum operador do Financeiro online"
                    : "Selecione"
                }
                disabled={type === "operator" && !operators.length}
                options={
                  type === "sector"
                    ? (directory?.sectors ?? [])
                        .filter((item) => item.code === "FIN")
                        .map((item) => ({
                          value: item.code,
                          label: item.name,
                        }))
                    : operators.map((item) => ({
                        value: item.key,
                        label: `${item.name} · ${item.windows_user}`,
                      }))
                }
              />
            </>
          )}
          {gnre && (
            <>
              <GnrePendingSelect value={cte} onSelect={setCte} />
              <div className="space-y-2">
                <Label htmlFor="chat-cte">CT-e</Label>
                <Input
                  id="chat-cte"
                  value={cte}
                  onChange={(event) => setCte(event.target.value)}
                  placeholder="10-10-2789"
                  pattern="[0-9]{1,4}-[0-9]{1,3}-[0-9]{1,10}"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="chat-chamado">Chamado Novelis, se já existir</Label>
                <Input
                  id="chat-chamado"
                  value={chamado}
                  onChange={(event) => setChamado(event.target.value)}
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={30}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="chat-note">Mensagem</Label>
                <Textarea
                  id="chat-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  maxLength={2000}
                  placeholder="Solicito a guia GNRE e o comprovante de pagamento."
                />
              </div>
            </>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={close} disabled={save.isPending}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={save.isPending || (!selectedRoom && !recipientAvailable)}
            >
              {save.isPending ? "Enviando…" : gnre ? "Enviar solicitação" : "Abrir conversa"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
