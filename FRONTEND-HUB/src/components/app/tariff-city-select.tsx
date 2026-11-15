import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronsUpDown, X } from "lucide-react";
import { useApi } from "@/services";
import type { TariffCity } from "@/services/tariffs";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Button } from "@/components/ui/button";

export function TariffCitySelect({
  label,
  value,
  onChange,
}: {
  label: string;
  value: TariffCity | null;
  onChange(value: TariffCity | null): void;
}) {
  const { api, mode, baseUrl } = useApi();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setTerm(search), 250);
    return () => clearTimeout(timer);
  }, [search]);
  const q = useQuery({
    queryKey: ["tariff-cities", mode, baseUrl, term],
    queryFn: () => api.tariffCities(term),
    enabled: open,
    retry: 0,
    staleTime: 60000,
  });
  return (
    <div className="min-w-0 space-y-1.5">
      <label className="text-xs font-medium">{label}</label>
      <div className="flex gap-1">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-label={label}
              aria-expanded={open}
              className="w-full justify-between font-normal"
            >
              <span className="truncate">
                {value?.label ?? `Todas as ${label === "Origem" ? "origens" : "cidades"}`}
              </span>
              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[320px] p-0" align="start">
            <Command shouldFilter={false}>
              <CommandInput
                placeholder="UF ou município…"
                value={search}
                onValueChange={setSearch}
              />
              <CommandList>
                <CommandEmpty>
                  {q.isError
                    ? "Consulta de cidades indisponível."
                    : q.isFetching
                      ? "Buscando…"
                      : "Nenhum município encontrado."}
                </CommandEmpty>
                {(q.data ?? []).map((city) => (
                  <CommandItem
                    key={city.portal_id}
                    value={city.portal_id}
                    onSelect={() => {
                      onChange(city);
                      setOpen(false);
                    }}
                  >
                    <Check
                      className={`mr-2 h-4 w-4 ${value?.portal_id === city.portal_id ? "opacity-100" : "opacity-0"}`}
                    />
                    {city.label}
                  </CommandItem>
                ))}
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
        {value && (
          <Button
            size="icon"
            variant="ghost"
            aria-label={`Limpar ${label.toLowerCase()}`}
            onClick={() => onChange(null)}
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
