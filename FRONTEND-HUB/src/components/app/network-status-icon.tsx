import { Cable, Network, ShieldCheck, SignalHigh, Unplug, Wifi } from "lucide-react";
import { networkLabel, type NetworkStatus } from "@/services/network-status";

const icons = {
  wifi: Wifi,
  ethernet: Cable,
  vpn: ShieldCheck,
  cellular: SignalHigh,
  offline: Unplug,
  unknown: Network,
};
export function NetworkStatusIcon({ value }: { value: NetworkStatus }) {
  const Icon = icons[value.kind];
  return (
    <span
      role="img"
      aria-label={networkLabel(value)}
      className="inline-flex shrink-0"
      data-network={value.kind}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
    </span>
  );
}
