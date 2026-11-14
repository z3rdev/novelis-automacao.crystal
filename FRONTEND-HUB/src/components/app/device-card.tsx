import { Monitor, Fingerprint } from "lucide-react";
import type { DeviceIdentity } from "@/services";
import { cn } from "@/lib/utils";

export function DeviceCard({
  identity,
  className,
}: {
  identity: DeviceIdentity | undefined;
  className?: string;
}) {
  return (
    <section className={cn("device-card", className)} aria-label="Identificação do dispositivo">
      <div className="mb-5 flex items-center gap-2 text-sm text-muted-foreground">
        <Monitor className="h-4 w-4" />
        Dispositivo
      </div>
      <h1 className="break-all text-3xl font-semibold tracking-tight">
        {identity?.computer_name ?? "Identificando…"}
      </h1>
      <div className="mt-6 space-y-1 text-sm">
        <p className="text-muted-foreground">Conta Windows</p>
        <p className="break-all font-medium">
          {identity?.windows_user ?? "Conectando ao backend local…"}
        </p>
      </div>
      <div className="mt-5 flex items-start gap-2 border-t border-primary/10 pt-4 text-xs text-muted-foreground">
        <Fingerprint className="mt-0.5 h-4 w-4 shrink-0" />
        <span className="break-all font-mono">
          MAC {identity ? identity.mac_addresses.join(" · ") || "indisponível" : "Identificando interfaces de rede…"}
        </span>
      </div>
    </section>
  );
}
