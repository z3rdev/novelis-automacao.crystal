import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { FluentIcon } from "../fluent-icon";
import { AppSelect } from "./app-select";

const hours = Array.from({ length: 24 }, (_, i) => ({
  value: String(i).padStart(2, "0"),
  label: String(i).padStart(2, "0"),
}));
const minutes = Array.from({ length: 60 }, (_, i) => ({
  value: String(i).padStart(2, "0"),
  label: String(i).padStart(2, "0"),
}));

export function AppTimePicker({
  value,
  onChange,
  label,
  id,
  disabled = false,
  className,
}: {
  value: string;
  onChange(value: string): void;
  label: string;
  id?: string;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [hour = "00", minute = "00"] = value.split(":");
  return (
    <Popover open={open && !disabled} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          id={id}
          variant="outline"
          disabled={disabled}
          aria-label={label}
          className={cn(
            "h-9 justify-between gap-3 bg-background px-3 font-normal tabular-nums",
            className,
          )}
        >
          {value || "00:00"}
          <FluentIcon name="clock" className="text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-56 p-3"
        aria-label={`Selecionar ${label.toLocaleLowerCase("pt-BR")}`}
      >
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1.5 text-xs">
            Hora
            <AppSelect
              label={`Hora: ${label}`}
              value={hour}
              onValueChange={(next) => onChange(`${next}:${minute}`)}
              options={hours}
            />
          </label>
          <label className="space-y-1.5 text-xs">
            Minuto
            <AppSelect
              label={`Minuto: ${label}`}
              value={minute}
              onValueChange={(next) => onChange(`${hour}:${next}`)}
              options={minutes}
            />
          </label>
        </div>
        <Button type="button" size="sm" className="mt-3 w-full" onClick={() => setOpen(false)}>
          Concluir
        </Button>
      </PopoverContent>
    </Popover>
  );
}
