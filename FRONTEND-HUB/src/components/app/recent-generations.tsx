import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TableBox } from "./page";
import { Pill, StagePill, type Tone } from "./status";
import { fmtDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { DacteJob } from "@/services";

export const jobKey = (job: DacteJob, index = 0) =>
  job.id || `${job.cte}-${job.metodo}-${job.geradoEm ?? ""}-${index}`;
export const documentCheck = (value?: string): [Tone, string] =>
  value === "ok"
    ? ["success", "OK"]
    : value === "falha"
      ? ["error", "Falha"]
      : ["warning", "Pendente"];

export function RecentGenerations({
  jobs,
  selected,
  onSelect,
}: {
  jobs: DacteJob[];
  selected: DacteJob | null;
  onSelect: (job: DacteJob, index: number) => void;
}) {
  return (
    <TableBox maxH="max-h-80 [&>div]:overflow-visible">
      <Table className="min-w-[860px] table-fixed whitespace-nowrap">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[110px]">CT-e</TableHead>
            <TableHead className="w-[80px]">Método</TableHead>
            <TableHead className="w-[120px]">Situação</TableHead>
            <TableHead className="w-[260px]">Etapa / erro</TableHead>
            <TableHead className="w-[60px]">QR</TableHead>
            <TableHead className="w-[75px]">Barras</TableHead>
            <TableHead className="w-[155px]">Data</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job, index) => (
            <TableRow
              key={jobKey(job, index)}
              className="cursor-pointer"
              onClick={() => onSelect(job, index)}
              data-state={selected === job ? "selected" : undefined}
            >
              <TableCell className="whitespace-nowrap font-mono">{job.cte}</TableCell>
              <TableCell>{job.metodo === "crystal" ? "Crystal" : "XML"}</TableCell>
              <TableCell>
                <StagePill s={job.state} />
              </TableCell>
              <TableCell>
                <div
                  title={job.erro ?? job.etapa}
                  className={cn("truncate", job.erro && "text-destructive")}
                >
                  {job.erro ?? job.etapa}
                </div>
              </TableCell>
              <TableCell>
                <Pill tone={documentCheck(job.qrCode)[0]}>{documentCheck(job.qrCode)[1]}</Pill>
              </TableCell>
              <TableCell>
                <Pill tone={documentCheck(job.codigoBarras)[0]}>
                  {documentCheck(job.codigoBarras)[1]}
                </Pill>
              </TableCell>
              <TableCell className="whitespace-nowrap">{fmtDateTime(job.geradoEm)}</TableCell>
            </TableRow>
          ))}
          {!jobs.length && (
            <TableRow>
              <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                Nenhuma geração registrada.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableBox>
  );
}
