import type { MonitoredDevice, MonitoredSession } from "@/services";
import { fmtDateTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TableBox } from "./page";
import { DeviceConnection, installationLabels, MonitorStatus } from "./monitor-status";
import { DeviceClassificationText } from "./monitor-classification";

export function DeviceTable({
  items,
  onSelect,
}: {
  items: MonitoredDevice[];
  onSelect(device: MonitoredDevice): void;
}) {
  return (
    <TableBox>
      <Table className="min-w-[1050px] [&_td]:whitespace-nowrap [&_th]:whitespace-nowrap">
        <TableHeader>
          <TableRow>
            <TableHead>Computador / setor</TableHead>
            <TableHead>Filial / estação</TableHead>
            <TableHead>Conexão</TableHead>
            <TableHead>Instalação / versão</TableHead>
            <TableHead>Operador conectado</TableHead>
            <TableHead>Automação</TableHead>
            <TableHead>Último contato</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id}>
              <TableCell>
                <span className="font-medium text-primary">{item.computer_name}</span>
                <div className="mt-1 max-w-60 truncate text-xs">
                  <DeviceClassificationText device={item} field="sector" />
                </div>
                <div className="mt-1 text-xs text-muted-foreground">{item.windows_user}</div>
              </TableCell>
              <TableCell>
                <DeviceClassificationText device={item} field="branch" />
                <div className="mt-1 text-xs text-muted-foreground">
                  <DeviceClassificationText device={item} field="station_type" />
                </div>
              </TableCell>
              <TableCell>
                <DeviceConnection online={item.online} />
              </TableCell>
              <TableCell>
                <span className="text-sm">{installationLabels[item.installation_kind]}</span>
                <div className="mt-1 font-mono text-xs text-muted-foreground">
                  {item.version ?? "Versão não informada"}
                </div>
              </TableCell>
              <TableCell>
                <div className="max-w-48 truncate" title={item.operators.join(", ")}>
                  {item.operators.join(", ") || "Sem sessão ativa"}
                </div>
              </TableCell>
              <TableCell>
                <MonitorStatus value={item.automation_status} muted={!item.online} />
                {!item.online && (
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    Último estado recebido
                  </div>
                )}
              </TableCell>
              <TableCell className="tabular-nums text-xs">
                {fmtDateTime(item.last_seen_at)}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Detalhes de ${item.computer_name}`}
                  onClick={() => onSelect(item)}
                >
                  Detalhes
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {!items.length && (
            <TableRow>
              <TableCell colSpan={8} className="py-12 text-center text-muted-foreground">
                Nenhum computador corresponde aos filtros.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableBox>
  );
}

export function SessionTable({ items }: { items: MonitoredSession[] }) {
  return (
    <TableBox>
      <Table className="min-w-[1100px] [&_td]:whitespace-nowrap [&_th]:whitespace-nowrap">
        <TableHeader>
          <TableRow>
            <TableHead>Operador / conta Windows</TableHead>
            <TableHead>Computador</TableHead>
            <TableHead>Sessão</TableHead>
            <TableHead>Automação</TableHead>
            <TableHead>Entrada</TableHead>
            <TableHead>Saída</TableHead>
            <TableHead>Último contato</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id}>
              <TableCell>
                <div className="font-medium text-primary">{item.operator_name}</div>
                <div className="mt-1 text-xs text-muted-foreground">{item.windows_user}</div>
              </TableCell>
              <TableCell>
                {item.computer_name}
                <div className="mt-1 max-w-60 truncate text-xs text-muted-foreground">
                  <DeviceClassificationText device={item} field="sector" /> ·{" "}
                  <DeviceClassificationText device={item} field="branch" />
                </div>
              </TableCell>
              <TableCell>
                <MonitorStatus value={item.display_status} />
              </TableCell>
              <TableCell>
                <MonitorStatus value={item.automation_status} muted={!item.online} />
              </TableCell>
              <TableCell className="tabular-nums text-xs">{fmtDateTime(item.login_at)}</TableCell>
              <TableCell className="tabular-nums text-xs">{fmtDateTime(item.logout_at)}</TableCell>
              <TableCell className="tabular-nums text-xs">
                {fmtDateTime(item.last_seen_at)}
              </TableCell>
            </TableRow>
          ))}
          {!items.length && (
            <TableRow>
              <TableCell colSpan={7} className="py-12 text-center text-muted-foreground">
                Nenhuma sessão corresponde aos filtros.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableBox>
  );
}
