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
  const widget = useQuery({
    queryKey: ["desktop-widget"],
    queryFn: () => desktop.widgetEnabled(),
    enabled: desktop.isDesktop,
    refetchInterval: 5_000,
    retry: 0,
  });
  const changeWidget = useMutation({
    mutationFn: (enabled: boolean) => desktop.setWidgetEnabled(enabled),
    onSuccess: (enabled) => qc.setQueryData(["desktop-widget"], enabled),
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
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
        <div className="flex items-center gap-3">
          <Label htmlFor="desktop-widget">Widget de agendamentos em segundo plano</Label>
          <Switch
            id="desktop-widget"
            checked={widget.data ?? false}
            disabled={!widget.isSuccess || changeWidget.isPending}
            onCheckedChange={(value) => changeWidget.mutate(value)}
          />
        </div>
        <Button
          variant="outline"
          disabled={!widget.data}
          onClick={() =>
            void desktop.showStatusWidget().catch((error: Error) => toast.error(error.message))
          }
        >
          Ver widget
        </Button>
      </div>
      {startup.isError && (
        <p role="alert" className="mt-2 text-sm text-destructive">
          Não foi possível consultar a inicialização com o Windows.
        </p>
      )}
    </Section>
  );
}
