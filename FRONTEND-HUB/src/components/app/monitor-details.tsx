import type { MonitoredDevice, MonitoredSession } from "@/services";
import { fmtDateTime } from "@/lib/format";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { DeviceConnection, installationLabels, MonitorStatus } from "./monitor-status";

export function MonitorDetails({
  device,
  sessions,
  onClose,
}: {
  device: MonitoredDevice | null;
  sessions: MonitoredSession[];
  onClose(): void;
}) {
  if (!device) return null;
  const rows = sessions.filter((item) => item.machine_id === device.machine_id);
  const fields = [
    ["Conta Windows", device.windows_user],
    ["Tipo", installationLabels[device.installation_kind]],
    ["Versão", device.version ?? "Não informada"],
    ["Pasta da aplicação", device.install_root ?? "Não informada"],
    ["Primeira detecção", fmtDateTime(device.first_seen_at)],
    ["Backend iniciado", fmtDateTime(device.backend_started_at)],
    ["Último contato", fmtDateTime(device.last_seen_at)],
    ["MACs informados", device.mac_addresses.join(" · ") || "Não informados"],
  ];
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{device.computer_name}</DialogTitle>
          <DialogDescription>Identificação recebida do backend deste computador.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-3">
          <DeviceConnection online={device.online} />
          <MonitorStatus value={device.automation_status} muted={!device.online} />
        </div>
        <dl className="grid gap-4 rounded-lg border bg-muted/30 p-4 sm:grid-cols-2">
          {fields.map(([label, value]) => (
            <div
              key={label}
              className={
                label === "Pasta da aplicação" || label === "MACs informados" ? "sm:col-span-2" : ""
              }
            >
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="mt-1 break-words text-sm font-medium [overflow-wrap:anywhere]">
                {value}
              </dd>
            </div>
          ))}
        </dl>
        <div>
          <h3 className="mb-3 text-sm font-semibold">Sessões recentes neste computador</h3>
          <div className="space-y-2">
            {rows.slice(0, 8).map((item) => (
              <div
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3"
              >
                <div>
                  <div className="text-sm font-medium">{item.operator_name}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {fmtDateTime(item.login_at)} · {item.windows_user}
                  </div>
                </div>
                <MonitorStatus value={item.display_status} />
              </div>
            ))}
            {!rows.length && (
              <p className="text-sm text-muted-foreground">
                Nenhuma sessão registrada para este computador.
              </p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
