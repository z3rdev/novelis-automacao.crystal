import rules from "../../../BACKEND/app/resources/device-naming.json";

export type ClassificationField = "sector" | "station_type" | "branch";
export interface NamedClassification {
  code: string;
  label: string;
}
export interface DeviceClassification {
  rules_version: number;
  source: "computer_name";
  sector: NamedClassification | null;
  station_type: NamedClassification | null;
  branch: NamedClassification | null;
  conflicts: ClassificationField[];
}
export interface ClassifiedDevice {
  computer_name: string;
  classification?: DeviceClassification;
}

export function classifyComputerName(name: string): DeviceClassification {
  const hostname = (name ?? "").trim().split(".")[0] ?? "";
  const tokens = hostname
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase()
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((token) => token.replace(/[0-9]+$/, ""));
  const result: DeviceClassification = {
    rules_version: rules.version,
    source: "computer_name",
    sector: null,
    branch: null,
    station_type: null,
    conflicts: [],
  };
  for (const field of ["sector", "station_type", "branch"] as const) {
    const candidates = field === "station_type" ? tokens.slice(0, 1) : tokens;
    const matches = rules[field].filter((rule) =>
      candidates.some((token) => rule.aliases.includes(token)),
    );
    if (matches.length === 1 && matches[0]) {
      result[field] = { code: matches[0].code, label: matches[0].label };
    } else if (matches.length > 1) result.conflicts.push(field);
  }
  return result;
}

export function deviceClassification(device: ClassifiedDevice): DeviceClassification {
  return device.classification ?? classifyComputerName(device.computer_name);
}
export function classificationLabel(
  value: DeviceClassification,
  field: ClassificationField,
): string {
  return value.conflicts.includes(field)
    ? "Conferir identificação"
    : (value[field]?.label ?? "Não identificado");
}
export function classificationSearch(device: ClassifiedDevice): string[] {
  const value = deviceClassification(device);
  return [value.sector?.label ?? "", value.branch?.label ?? "", value.station_type?.label ?? ""];
}
export const deviceNamingOptions = { sectors: rules.sector, branches: rules.branch };
