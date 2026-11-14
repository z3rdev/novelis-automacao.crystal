import { afterEach, describe, expect, it, vi } from "vitest";
import { createHttpApi } from "./http";

afterEach(() => { vi.unstubAllGlobals(); sessionStorage.clear(); });

describe("adaptador do backend central", () => {
  it("repete uma leitura quando ocorre timeout e recupera os dados", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new DOMException("signal timed out", "TimeoutError"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ naFila: 8 }), { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    expect(await createHttpApi("http://server/api/hub").getOverview()).toEqual({ naFila: 8 });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("informa o timeout em portugues depois da tentativa de recuperacao", async () => {
    const fetcher = vi.fn().mockRejectedValue(new DOMException("signal timed out", "TimeoutError"));
    vi.stubGlobal("fetch", fetcher);
    await expect(createHttpApi("http://server/api/hub").listCtes()).rejects.toThrow("A consulta ao backend demorou além do esperado");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("mantem uma unica solicitacao de execucao quando ocorre timeout", async () => {
    const fetcher = vi.fn().mockRejectedValue(new DOMException("signal timed out", "TimeoutError"));
    vi.stubGlobal("fetch", fetcher);
    await expect(createHttpApi("http://server/api/hub").startRun({ flow: "completo" })).rejects.toThrow("A consulta ao backend demorou");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("envia zero para a consulta do dia atual", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    await createHttpApi("http://server/api/hub").refreshCtes(0);
    expect(JSON.parse(fetcher.mock.calls[0]![1].body)).toEqual({ periodoDias: 0 });
  });

  it("vincula as chamadas a sessao recebida e remove o identificador ao sair", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ session: { id: "unit-session" } }), { status: 200 }))
      .mockResolvedValueOnce(new Response("{}", { status: 200 })).mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetcher);
    const api = createHttpApi("http://server/api/hub");
    await api.login("Operador de teste");
    await api.refreshCtes(5);
    expect(fetcher.mock.calls[1]![1].headers["X-Operator-Session"]).toBe("unit-session");
    await api.logout();
    expect(sessionStorage.getItem("novelis.operator-session:http://server/api/hub")).toBeNull();
  });
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
