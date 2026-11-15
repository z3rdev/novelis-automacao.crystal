import { AppDatePicker } from "./fields/app-date-picker";
import { Label } from "@/components/ui/label";
import { PeriodSelect } from "./period-select";
import { dateLimits, periodError, type DateRange } from "@/services/consultation";
import { useId, type ReactNode } from "react";

export function ConsultationPeriod({
  value,
  onChange,
  range,
  onRangeChange,
  disabled = false,
  children,
}: {
  value: number;
  onChange(value: number): void;
  range: DateRange;
  onRangeChange(value: DateRange): void;
  disabled?: boolean;
  children?: ReactNode;
}) {
  const limits = dateLimits();
  const id = useId();
  return (
    <div className="flex max-w-full flex-wrap items-end gap-3" data-testid="consultation-toolbar">
      <div className="w-60 max-w-full space-y-1.5">
        <Label className="text-xs" htmlFor={`${id}-period`}>
          Período
        </Label>
        <PeriodSelect
          id={`${id}-period`}
          className="w-full"
          value={value}
          onChange={onChange}
          disabled={disabled}
          custom
        />
      </div>
      {value === -1 && (
        <div className="flex w-[332px] max-w-full gap-3">
          <div className="min-w-0 flex-1 space-y-1.5">
            <Label className="text-xs" htmlFor={`${id}-start`}>
              De
            </Label>
            <AppDatePicker
              label="De"
              className="h-9 min-w-0"
              id={`${id}-start`}
              {...limits}
              value={range.dataInicio}
              disabled={disabled}
              onChange={(date) => onRangeChange({ ...range, dataInicio: date })}
            />
          </div>
          <div className="min-w-0 flex-1 space-y-1.5">
            <Label className="text-xs" htmlFor={`${id}-end`}>
              Até
            </Label>
            <AppDatePicker
              label="Até"
              className="h-9 min-w-0"
              id={`${id}-end`}
              {...limits}
              value={range.dataFim}
              disabled={disabled}
              onChange={(date) => onRangeChange({ ...range, dataFim: date })}
            />
          </div>
        </div>
      )}
      {children && (
        <div className="flex min-h-9 max-w-full flex-wrap items-center gap-2 [&_button]:h-9 [&_a]:h-9">
          {children}
        </div>
      )}
      {value === -1 && periodError(range) && (
        <p role="alert" className="w-full text-xs text-destructive">
          {periodError(range)}
        </p>
      )}
    </div>
  );
}
