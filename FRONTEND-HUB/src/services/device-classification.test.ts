import { describe, expect, it } from "vitest";
import cases from "../../../BACKEND/tests/fixtures/device-naming-cases.json";
import {
  classificationLabel,
  classifyComputerName,
  deviceClassification,
} from "./device-classification";

describe("identificação pelo nome do computador", () => {
  it.each(cases)("$name", (example) => {
    const value = classifyComputerName(example.name);
    for (const field of ["sector", "station_type", "branch"] as const) {
      expect(value[field]?.code ?? null).toBe(example[field]);
    }
    expect(value.conflicts).toEqual(example.conflicts ?? []);
  });
  it("preserva a classificação do servidor e atende clientes nativos anteriores", () => {
    const classification = classifyComputerName("WKS-COMP-VIN-01");
    expect(deviceClassification({ computer_name: "UNKNOWN", classification })).toBe(classification);
    expect(deviceClassification({ computer_name: "NB-COM-VIN-01" }).sector?.label).toBe(
      "Comercial",
    );
    expect(classificationLabel(classifyComputerName("UNKNOWN"), "sector")).toBe("Não identificado");
    expect(classificationLabel(classifyComputerName("NB-TI-COM-01"), "sector")).toBe(
      "Conferir identificação",
    );
  });
});
