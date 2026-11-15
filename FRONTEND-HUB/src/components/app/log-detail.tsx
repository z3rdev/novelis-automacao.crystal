import { Copy } from "lucide-react";
import { toast } from "sonner";
import type { LogEntry } from "@/services";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { fmtDateTime } from "@/lib/format";
import { eventDetails, logCategory, logLevels, safeEventDetails } from "./log-presentation";

export function LogDetail({ entry, onClose }: { entry: LogEntry | null; onClose(): void }) {
  const data = entry ? safeEventDetails(eventDetails(entry)) : null;
  async function copy() {
    if (!entry) return;
    try {
      await navigator.clipboard.writeText(
        JSON.stringify(
          {
            time: entry.time,
            severity: entry.severity,
            source: entry.source,
            message: entry.message,
            details: data,
          },
          null,
          2,
        ),
      );
      toast.success("Detalhes copiados.");
    } catch {
      toast.error("Não foi possível copiar.");
    }
  }
  return (
    <Sheet
      open={Boolean(entry)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-xl">
        {entry && (
          <>
            <SheetHeader className="border-b px-6 pb-5 pt-8">
              <SheetTitle className="text-xl">Detalhes do evento</SheetTitle>
              <SheetDescription>
                {fmtDateTime(entry.time)} · {logCategory(entry.source)}
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-6 p-6">
              <div className="flex items-center justify-between gap-3">
                <span className={`text-sm font-medium ${logLevels[entry.severity].color}`}>
                  {logLevels[entry.severity].label}
                </span>
                <Button variant="outline" size="sm" onClick={() => void copy()}>
                  <Copy />
                  Copiar detalhes
                </Button>
              </div>
              <p className="break-words text-sm leading-7 [overflow-wrap:anywhere]">
                {entry.message}
              </p>
              <dl className="border-y py-4 text-sm">
                <dt className="text-xs text-muted-foreground">Origem técnica</dt>
                <dd className="mt-2 break-all font-mono text-xs">{entry.source}</dd>
              </dl>
              {data !== null && (
                <section>
                  <h3 className="mb-3 text-sm font-medium">Dados do evento</h3>
                  {typeof data === "object" && !Array.isArray(data) ? (
                    <dl className="space-y-4">
                      {Object.entries(data as Record<string, unknown>).map(([key, value]) => (
                        <div key={key}>
                          <dt className="mb-1 text-xs text-muted-foreground">{key}</dt>
                          <dd className="break-words whitespace-pre-wrap text-sm [overflow-wrap:anywhere]">
                            {typeof value === "object"
                              ? JSON.stringify(value, null, 2)
                              : String(value ?? "—")}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  ) : (
                    <pre className="whitespace-pre-wrap break-words rounded-md bg-muted/50 p-4 text-xs">
                      {typeof data === "string" ? data : JSON.stringify(data, null, 2)}
                    </pre>
                  )}
                </section>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
