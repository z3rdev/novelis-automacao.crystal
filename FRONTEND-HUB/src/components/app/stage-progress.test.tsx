import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StagesView } from "./stage-progress";
import type { RunStatus } from "@/services";

describe("etapas de uma execucao cancelada", () => {
  it("preserva os contadores e nao apresenta etapa executando", () => {
    const run: RunStatus = {
      id: "cancelled", flow: "consulta", state: "cancelada", etapaAtual: "consulta", cteAtual: null,
      processados: 0, total: 442, iniciadoEm: null,
      stages: [
        { id: "consulta", state: "cancelada", done: 0, total: 442 },
        ...(["pdf", "xml", "comprovantes", "chamados"] as const).map((id) => ({ id, state: "ignorada" as const, done: 0, total: 0 })),
      ],
    };
    render(<StagesView run={run} />);
    expect(screen.getByText("Cancelada")).toBeInTheDocument();
    expect(screen.getByText("0 de 442")).toBeInTheDocument();
    expect(screen.queryByText("Executando")).not.toBeInTheDocument();
    expect(screen.getAllByText("Fora do fluxo")).toHaveLength(4);
  });
});
