import {
  classificationLabel,
  deviceClassification,
  deviceNamingOptions,
  type ClassifiedDevice,
  type ClassificationField,
} from "@/services/device-classification";
import { AppSelect } from "./fields/app-select";

export function DeviceClassificationText({
  device,
  field,
}: {
  device: ClassifiedDevice;
  field: ClassificationField;
}) {
  const value = classificationLabel(deviceClassification(device), field);
  return <span title={value}>{value}</span>;
}

export function ClassificationFilters({
  sector,
  branch,
  onSector,
  onBranch,
}: {
  sector: string;
  branch: string;
  onSector(value: string): void;
  onBranch(value: string): void;
}) {
  return (
    <>
      <AppSelect
        label="Filtrar setor"
        className="w-full sm:w-64"
        value={sector}
        onValueChange={onSector}
        options={[
          { value: "all", label: "Todos os setores" },
          ...deviceNamingOptions.sectors.map((item) => ({ value: item.code, label: item.label })),
          { value: "unknown", label: "Setor não identificado" },
        ]}
      />
      <AppSelect
        label="Filtrar filial"
        className="w-full sm:w-48"
        value={branch}
        onValueChange={onBranch}
        options={[
          { value: "all", label: "Todas as filiais" },
          ...deviceNamingOptions.branches.map((item) => ({ value: item.code, label: item.label })),
          { value: "unknown", label: "Filial não identificada" },
        ]}
      />
    </>
  );
}
