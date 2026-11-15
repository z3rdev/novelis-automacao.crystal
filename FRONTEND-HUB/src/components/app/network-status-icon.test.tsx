import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { NetworkKind } from "@/services/network-status";
import { NetworkStatusIcon } from "./network-status-icon";

afterEach(cleanup);
it.each<[NetworkKind, string]>([
  ["wifi", "Wi-Fi"],
  ["ethernet", "Rede cabeada"],
  ["vpn", "VPN"],
  ["cellular", "Rede móvel"],
  ["offline", "Sem rede ativa"],
  ["unknown", "Rede não identificada"],
])("representa a conexão %s", (kind, name) => {
  render(<NetworkStatusIcon value={{ kind, transport: null }} />);
  expect(screen.getByRole("img", { name })).toHaveAttribute("data-network", kind);
});
it("identifica VPN e a conexão utilizada por baixo do túnel", () => {
  render(<NetworkStatusIcon value={{ kind: "vpn", transport: "wifi" }} />);
  expect(screen.getByRole("img", { name: "VPN · Wi-Fi" })).toHaveAttribute("data-network", "vpn");
});
