import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Monitor, Minimize2 } from "lucide-react";
import { toast } from "sonner";
import { desktop } from "@/services/desktop";
import { Section } from "./page";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";

export function DesktopSettings() {
  const qc = useQueryClient();
  const startup = useQuery({
    queryKey: ["desktop-startup"],
    queryFn: () => desktop.startupEnabled(),
    enabled: desktop.isDesktop,
    retry: 0,
  });
  const change = useMutation({
    mutationFn: (enabled: boolean) => desktop.setStartup(enabled),
    onSuccess: (enabled) => {
      qc.setQueryData(["desktop-startup"], enabled);
      toast.success(
        enabled
          ? "O Cargo Hub iniciará com o Windows em segundo plano."
          : "Inicialização com o Windows desativada.",
      );
    },
    onError: (error: Error) => toast.error(error.message),
  });
  if (!desktop.isDesktop) return null;
  return (
    <Section title="Aplicativo e inicialização">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <Monitor className="h-5 w-5 text-muted-foreground" />
            <Label htmlFor="desktop-startup">Iniciar com o Windows</Label>
            <Switch
              id="desktop-startup"
              checked={startup.data ?? false}
              disabled={!startup.isSuccess || change.isPending}
              onCheckedChange={(enabled) => change.mutate(enabled)}
            />
          </div>
          <p className="max-w-xl text-xs text-muted-foreground">
            Ao entrar nesta conta Windows, o Cargo Hub ficará na bandeja com os agendamentos ativos.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() =>
            void desktop.hideToTray().catch((error: Error) => toast.error(error.message))
          }
        >
          <Minimize2 />
          Manter em segundo plano
        </Button>
      </div>
      <p className="mt-4 text-xs text-muted-foreground">
        Fechar a janela pelo X mantém o aplicativo na bandeja. Use Abrir Cargo Hub para voltar ou
        Sair do Cargo Hub para encerrar.
      </p>
      {startup.isError && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          Não foi possível consultar a inicialização com o Windows.
        </p>
      )}
    </Section>
  );
}
