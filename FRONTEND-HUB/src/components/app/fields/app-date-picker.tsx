import { useState } from "react";
import { ptBR } from "date-fns/locale";
import { Calendar } from "@/components/ui/calendar";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { localDate } from "@/services/consultation";
import { FluentIcon } from "../fluent-icon";

function parseLocalDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return undefined;
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year!, month! - 1, day);
  return localDate(date) === value ? date : undefined;
}

export function AppDatePicker({
  value,
  onChange,
  label,
  id,
  min,
  max,
  disabled = false,
  className,
}: {
  value: string;
  onChange(value: string): void;
  label: string;
  id?: string | undefined;
  min?: string;
  max?: string;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const selected = parseLocalDate(value);
  const earliest = min ? parseLocalDate(min) : undefined;
  const latest = max ? parseLocalDate(max) : undefined;
  return (
    <Popover open={open && !disabled} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          id={id}
          aria-label={label}
          disabled={disabled}
          className={cn(
            "h-9 w-full min-w-0 justify-between gap-2 bg-background px-3 font-normal tabular-nums",
            className,
          )}
        >
          <span className={cn("truncate", !selected && "text-muted-foreground")}>
            {selected ? selected.toLocaleDateString("pt-BR") : "Selecionar data"}
          </span>
          <FluentIcon name="calendar" className="shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-auto max-w-[calc(100vw-24px)] p-0"
        aria-label={`Calendário: ${label}`}
      >
        <Calendar
          autoFocus
          mode="single"
          locale={ptBR}
          labels={{
            labelNav: () => "Navegação do calendário",
            labelPrevious: () => "Mês anterior",
            labelNext: () => "Próximo mês",
          }}
          selected={selected}
          defaultMonth={selected ?? latest ?? new Date()}
          {...(earliest ? { startMonth: earliest } : {})}
          {...(latest ? { endMonth: latest } : {})}
          disabled={(date) => Boolean((earliest && date < earliest) || (latest && date > latest))}
          onSelect={(date) => {
            if (date) {
              onChange(localDate(date));
              setOpen(false);
            }
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
