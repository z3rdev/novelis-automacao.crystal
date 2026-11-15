import { Button } from "@/components/ui/button";
import { AppDatePicker } from "./app-date-picker";
import { AppTimePicker } from "./app-time-picker";

export function AppDateTimePicker({
  value,
  onChange,
  id,
  label,
}: {
  value: string;
  onChange(value: string): void;
  id?: string;
  label: string;
}) {
  const [date = "", time = "00:00"] = value.split("T");
  return (
    <div className="flex min-w-0 items-center gap-2">
      <AppDatePicker
        id={id}
        label={label}
        value={date}
        onChange={(next) => onChange(`${next}T${time}`)}
      />
      <AppTimePicker
        label={`Horário: ${label}`}
        value={time}
        disabled={!date}
        onChange={(next) => onChange(`${date}T${next}`)}
      />
      {value && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => onChange("")}
          aria-label={`Limpar ${label.toLocaleLowerCase("pt-BR")}`}
        >
          Limpar
        </Button>
      )}
    </div>
  );
}
