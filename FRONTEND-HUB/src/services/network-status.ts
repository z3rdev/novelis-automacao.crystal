export type NetworkKind = "wifi" | "ethernet" | "vpn" | "cellular" | "offline" | "unknown";
export interface NetworkStatus {
  kind: NetworkKind;
  transport: NetworkKind | null;
}
export const networkLabels: Record<NetworkKind, string> = {
  wifi: "Wi-Fi",
  ethernet: "Rede cabeada",
  vpn: "VPN",
  cellular: "Rede móvel",
  offline: "Sem rede ativa",
  unknown: "Rede não identificada",
};
export function networkLabel(value: NetworkStatus) {
  return value.kind === "vpn" && value.transport
    ? `VPN · ${networkLabels[value.transport]}`
    : networkLabels[value.kind];
}
