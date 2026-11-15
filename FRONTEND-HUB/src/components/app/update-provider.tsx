import { createContext, useContext, useEffect, useRef, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { toast } from "sonner";
import { useApi, type UpdateStatus } from "@/services";
import { Button } from "@/components/ui/button";
import { UpdateDialog } from "./update-dialog";
import { useAppDialogs } from "./app-dialogs";
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";

const UpdateContext = createContext<{ show(): void; available: boolean } | null>(null);

export function UpdateProvider({ children }: { children: ReactNode }) {
  const { api, mode, baseUrl } = useApi();
  const qc = useQueryClient();
  const key = ["updates", mode, baseUrl];
  const dialogs = useAppDialogs();
  const open = dialogs.active === "updates";
  const dismissed = useRef("");
  const status = useQuery({
    queryKey: key,
    queryFn: () => api.getUpdateStatus(),
    enabled: mode === "local",
    retry: 0,
    refetchInterval: (query) => (query.state.data?.status === "downloading" ? 1000 : 30000),
  });
  const run = useQuery({
    queryKey: ["run", mode, baseUrl],
    queryFn: () => api.getRun(),
    enabled: open && mode === "local",
    refetchInterval: 3000,
    retry: 0,
  });
  const save = (value: UpdateStatus) => qc.setQueryData(key, value);
  const error = (value: Error) => toast.error(value.message);
  const check = useMutation({
    mutationFn: () => api.checkUpdates(),
    onSuccess: save,
    onError: error,
  });
  const download = useMutation({
    mutationFn: () => api.downloadUpdate(),
    onSuccess: save,
    onError: error,
  });
  const install = useMutation({
    mutationFn: () => api.installUpdate(),
    onSuccess: save,
    onError: error,
  });
  const checkRef = useRef(check.mutate);
  checkRef.current = check.mutate;
  useEffect(() => {
    if (mode !== "local") return;
    const first = window.setTimeout(() => checkRef.current(), 2000);
    const timer = window.setInterval(() => checkRef.current(), 300000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [mode, baseUrl]);
  const releaseId = status.data?.release?.sha256 ?? "";
  useEffect(() => {
    if (
      status.data?.status === "available" &&
      releaseId &&
      dismissed.current !== releaseId &&
      dialogs.active === null
    )
      dialogs.show("updates");
  }, [releaseId, status.data?.status, dialogs.active, dialogs.show]);
  const changeOpen = (value: boolean) => {
    if (!value) dismissed.current = releaseId;
    if (value) dialogs.show("updates");
    else dialogs.hide("updates");
  };
  const available = ["available", "downloading", "ready"].includes(status.data?.status ?? "");
  return (
    <UpdateContext.Provider
      value={{
        show: () => {
          dialogs.show("updates");
          if (!available && !check.isPending) check.mutate();
        },
        available,
      }}
    >
      {children}
      <UpdateDialog
        open={open}
        onOpenChange={changeOpen}
        data={status.data}
        checking={check.isPending}
        busy={download.isPending || install.isPending}
        automationRunning={["executando", "parando"].includes(run.data?.state ?? "")}
        onCheck={() => check.mutate()}
        onDownload={() => download.mutate()}
        onInstall={() => install.mutate()}
      />
    </UpdateContext.Provider>
  );
}

export function UpdateButton({
  sidebar = false,
  onlyAvailable = false,
}: {
  sidebar?: boolean;
  onlyAvailable?: boolean;
}) {
  const context = useContext(UpdateContext);
  const { mode } = useApi();
  if (!context || mode !== "local") return null;
  if (onlyAvailable && !context.available) return null;
  const label = context.available ? "Nova versão disponível" : "Atualizações";
  if (sidebar)
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton onClick={context.show} tooltip={label} aria-label={label}>
            <Download className="h-4 w-4" />
            <span>{label}</span>
            {context.available && <span className="ml-auto h-2 w-2 rounded-full bg-teal-400" />}
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  return (
    <Button size="sm" variant={context.available ? "default" : "ghost"} onClick={context.show}>
      <Download className="h-4 w-4" />
      {context.available ? "Nova versão" : "Atualizações"}
    </Button>
  );
}
