import { useMutation, useQuery } from "@tanstack/react-query";
import { Code2, Loader2, Server } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/services";
import { Button } from "@/components/ui/button";
import { Section } from "./page";
import { ReleasePublisher } from "./release-publisher";

export function DeveloperSettings() {
  const { api, mode, baseUrl } = useApi();
  const config = useQuery({
    queryKey: ["developer-config", mode, baseUrl],
    queryFn: () => api.getDeveloperConfig(),
    enabled: mode === "local",
    refetchInterval: 15000,
    retry: 0,
  });
  const probe = useMutation({
    mutationFn: () => api.testReleaseConnection(),
    onError: (error: Error) => toast.error(error.message),
  });
  if (!config.data?.enabled || mode !== "local") return null;
  return (
    <Section
      title="Desenvolvedor"
      actions={
        <span className="inline-flex items-center gap-1 text-xs text-accent-foreground">
          <Code2 className="h-4 w-4" />
          Ativo neste computador
        </span>
      }
    >
      <dl className="grid gap-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs text-muted-foreground">Servidor S3</dt>
          <dd className="mt-1 break-all font-mono">{config.data.endpoint}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Destino das releases</dt>
          <dd className="mt-1 font-mono">
            {config.data.bucket}/{config.data.prefix}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs text-muted-foreground">Manifesto consultado pelo aplicativo</dt>
          <dd className="mt-1 break-all font-mono text-xs">{config.data.manifest_url}</dd>
        </div>
      </dl>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button variant="outline" onClick={() => probe.mutate()} disabled={probe.isPending}>
          {probe.isPending ? <Loader2 className="animate-spin" /> : <Server />}Testar conexão de
          releases
        </Button>
        {probe.data && (
          <p
            role="status"
            className={
              probe.data.authenticated ? "text-sm text-success" : "text-sm text-destructive"
            }
          >
            {probe.data.message}
            {probe.data.authenticated &&
              !probe.data.manifest_present &&
              " O manifesto latest.json ainda precisa ser publicado."}
          </p>
        )}
      </div>
      <ReleasePublisher />
    </Section>
  );
}
