import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { UpdateStatus } from "@/services";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppDialogs } from "./app-dialogs";
import { UpdateButton, UpdateProvider } from "./update-provider";

const fixture = vi.hoisted(() => ({
  api: { getUpdateStatus: vi.fn(), getRun: vi.fn(), checkUpdates: vi.fn() },
}));
vi.mock("@/services", () => ({
  useApi: () => ({ api: fixture.api, mode: "local", baseUrl: "fixture" }),
}));
vi.mock("./update-dialog", () => ({ UpdateDialog: () => null }));
const clients: QueryClient[] = [];
beforeEach(() => {
  fixture.api.getUpdateStatus.mockResolvedValue({ status: "up_to_date" });
  fixture.api.getRun.mockResolvedValue({ state: "aguardando" });
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((client) => client.clear());
});

it("exibe o atalho do rodapé apenas quando existe uma atualização e mantém a consulta manual", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <AppDialogs>
        <UpdateProvider>
          <SidebarProvider>
            <UpdateButton sidebar onlyAvailable />
            <UpdateButton />
          </SidebarProvider>
        </UpdateProvider>
      </AppDialogs>
    </QueryClientProvider>,
  );
  await screen.findByRole("button", { name: "Atualizações" });
  await waitFor(() =>
    expect(client.getQueryData(["updates", "local", "fixture"])).toEqual({ status: "up_to_date" }),
  );
  expect(screen.queryByRole("button", { name: "Nova versão disponível" })).not.toBeInTheDocument();
  await act(async () => {
    client.setQueryData<Partial<UpdateStatus>>(["updates", "local", "fixture"], {
      status: "ready",
    });
  });
  expect(await screen.findByRole("button", { name: "Nova versão disponível" })).toBeInTheDocument();
});
