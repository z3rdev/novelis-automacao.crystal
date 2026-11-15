import { Monitor, Fingerprint } from "lucide-react";
import type { DeviceIdentity } from "@/services";
import { cn } from "@/lib/utils";
import { classificationLabel, deviceClassification } from "@/services/device-classification";

export function DeviceCard({
  identity,
  className,
}: {
  identity: DeviceIdentity | undefined;
  className?: string;
}) {
  const classification = identity ? deviceClassification(identity) : null;
  return (
    <section className={cn("device-card", className)} aria-label="Identificação do dispositivo">
      <div className="flex items-start gap-3">
        <Monitor className="mt-1 h-5 w-5 shrink-0 text-muted-foreground" />
        <h1 className="text-xl font-semibold tracking-tight">
          {classification
            ? classification.sector || classification.conflicts.includes("sector")
              ? classificationLabel(classification, "sector")
              : "Setor não identificado"
            : "Identificando setor…"}
        </h1>
      </div>
      <p className="mt-2 break-all text-sm text-muted-foreground">
        {identity?.computer_name ?? "Identificando dispositivo…"}
      </p>
      <div className="mt-6 space-y-1 text-sm">
        <p className="text-muted-foreground">Conta Windows</p>
        <p className="break-all font-medium">
          {identity?.windows_user ?? "Conectando ao backend local…"}
        </p>
      </div>
      <div className="mt-5 flex items-start gap-2 border-t border-primary/10 pt-4 text-xs text-muted-foreground">
        <Fingerprint className="mt-0.5 h-4 w-4 shrink-0" />
        <span className="break-all font-mono">
          MAC{" "}
          {identity
            ? identity.mac_addresses.join(" · ") || "indisponível"
            : "Identificando interfaces de rede…"}
        </span>
      </div>
    </section>
  );
}
