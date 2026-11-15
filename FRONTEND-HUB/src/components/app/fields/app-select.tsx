import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface AppSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export function AppSelect({
  value,
  onValueChange,
  options,
  label,
  placeholder,
  id,
  disabled = false,
  className,
}: {
  value: string;
  onValueChange(value: string): void;
  options: AppSelectOption[];
  label: string;
  placeholder?: string;
  id?: string;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <Select value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger
        id={id}
        aria-label={label}
        className={cn("min-w-0 gap-3 bg-background [&>span:first-child]:truncate", className)}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className="max-w-[calc(100vw-24px)]">
        {options.map((option) => (
          <SelectItem
            key={option.value}
            value={option.value}
            disabled={option.disabled}
            className="break-words"
          >
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
