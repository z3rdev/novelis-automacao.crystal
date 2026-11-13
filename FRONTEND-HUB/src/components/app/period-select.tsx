import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const consultationPeriods = [
  { value: 0, label: "Dia atual" },
  { value: 5, label: "Últimos 5 dias" },
  { value: 10, label: "Últimos 10 dias" },
  { value: 20, label: "Últimos 20 dias" },
  { value: 30, label: "Últimos 30 dias" },
];

export function PeriodSelect({
  value,
  onChange,
  disabled = false,
}: {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <Select
      value={String(value)}
      onValueChange={(value) => onChange(Number(value))}
      disabled={disabled}
    >
      <SelectTrigger className="w-44" aria-label="Período da consulta">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {consultationPeriods.map((period) => (
          <SelectItem key={period.value} value={String(period.value)}>
            {period.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
