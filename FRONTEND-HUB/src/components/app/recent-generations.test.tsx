import { describe, expect, it } from "vitest";
import type { DacteJob } from "@/services";
import { jobKey } from "./recent-generations";

const job: DacteJob = {
  cte: "2-10-17437", metodo: "crystal", state: "concluida", etapa: "Concluído",
};

describe("identificação das gerações recentes", () => {
  it("preserva o identificador real quando a ordem da lista muda", () => {
    expect(jobKey({ ...job, id: "stable-job" }, 0)).toBe(jobKey({ ...job, id: "stable-job" }, 1));
  });

  it("distingue registros legados repetidos sem identificador", () => {
    expect(jobKey(job, 0)).not.toBe(jobKey(job, 1));
  });
});
