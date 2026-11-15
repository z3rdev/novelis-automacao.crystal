import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const consultationPeriods = [
  { value: 0, label: "Dia atual" },
  { value: 2, label: "Últimos 2 dias" },
  { value: 5, label: "Últimos 5 dias" },
  { value: 10, label: "Últimos 10 dias" },
  { value: 20, label: "Últimos 20 dias" },
  { value: 30, label: "Últimos 30 dias" },
];

export function PeriodSelect({
  value,
  onChange,
  disabled = false,
  custom = false,
  id,
  className,
}: {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  custom?: boolean;
  id?: string;
  className?: string;
}) {
  return (
    <Select
      value={String(value)}
      onValueChange={(value) => onChange(Number(value))}
      disabled={disabled}
    >
      <SelectTrigger id={id} className={`h-9 ${className ?? "w-60"}`} aria-label="Período da consulta">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {custom && <SelectItem value="-1">Período personalizado</SelectItem>}
        {consultationPeriods.map((period) => (
          <SelectItem key={period.value} value={String(period.value)}>
            {period.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
