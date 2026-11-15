import { useQuery } from "@tanstack/react-query";
import { useApi } from "@/services";
import { AppSelect } from "../fields/app-select";

export function GnrePendingSelect({
  value,
  onSelect,
}: {
  value: string;
  onSelect(cte: string): void;
}) {
  const { api, mode, baseUrl } = useApi();
  const query = useQuery({
    queryKey: ["ctes", mode, baseUrl],
    queryFn: () => api.listCtes(),
    refetchInterval: 15_000,
    retry: 0,
  });
  const rows = (query.data ?? []).filter((row) => row.comprovante === "faltando");
  return (
    <div className="space-y-2">
      <AppSelect
        label="CT-es pendentes de GNRE e comprovante"
        value={rows.some((row) => row.id === value) ? value : ""}
        placeholder={query.isPending ? "Carregando pendentes…" : "Selecionar CT-e pendente"}
        onValueChange={onSelect}
        options={rows.map((row) => ({
          value: row.id,
          label: `${row.id} · ${row.origem || "Origem"} → ${row.destino || "Destino"}`,
        }))}
      />
      {query.isError ? (
        <p role="alert" className="text-xs text-destructive">
          Não foi possível carregar os pendentes.
        </p>
      ) : !query.isPending && !rows.length ? (
        <p className="text-xs text-muted-foreground">Nenhum CT-e aguardando esses documentos.</p>
      ) : null}
    </div>
  );
}
