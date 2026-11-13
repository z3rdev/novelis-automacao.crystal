import { afterEach, describe, expect, it, vi } from "vitest";
import { createHttpApi } from "./http";

afterEach(() => vi.unstubAllGlobals());

describe("adaptador do backend central", () => {
  it("envia toda a lista na mesma execucao", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    await createHttpApi("http://server/api/hub/").startRun({ flow: "somente_pdf", ctes: ["2-10-10402", "11-10-397"] });
    const [url, init] = fetcher.mock.calls[0]!;
    expect(url).toBe("http://server/api/hub/runs");
    expect(JSON.parse(init.body)).toEqual({ flow: "somente_pdf", ctes: ["2-10-10402", "11-10-397"] });
  });

  it("propaga falha real sem trocar para dados de demonstracao", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Outro lote ativo" }), { status: 409 })));
    await expect(createHttpApi("http://server/api/hub").startRun({ flow: "completo" })).rejects.toThrow("Outro lote ativo");
  });

  it("abre PDF pelo identificador estavel fornecido pela API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([
      { id: "stable-id", cte: "2-10-10402", state: "concluida", arquivo: "D:\\server\\document.pdf" },
      { id: "failed-id", cte: "11-10-397", state: "falhou" },
    ]), { status: 200 })));
    const jobs = await createHttpApi("http://server/api/hub").listDacteJobs();
    expect(jobs[0]?.pdfUrl).toBe("http://server/api/hub/documents/dacte/file/stable-id");
    expect(jobs[1]?.pdfUrl).toBeUndefined();
  });
});
