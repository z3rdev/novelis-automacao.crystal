import {
  mkdir,
  readFile,
  writeFile,
  rename,
  open,
  unlink,
} from "node:fs/promises";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  keyParts,
  statusRequest,
  distributionRequest,
  result,
  documents,
  distributionUrl,
  svspUrl,
} from "./protocol.js";
import { soap } from "./transport.js";

const args = process.argv.slice(2);
function option(name: string, fallback: string) {
  const index = args.indexOf(name);
  return index < 0 ? fallback : (args[index + 1] ?? fallback);
}
async function json(path: string, fallback: object) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return fallback;
    throw error;
  }
}
async function atomic(path: string, content: string) {
  await writeFile(path + ".part", content);
  await rename(path + ".part", path);
}

async function main() {
  const command = args[0],
    key = option("--key", ""),
    parts = keyParts(key);
  if (command === "validate") {
    console.log(JSON.stringify({ valid: true, ...parts }));
    return;
  }
  if (!["status", "dist", "nsu"].includes(command))
    throw new Error("Use validate, status, dist ou nsu com --key.");
  const environment = option("--environment", "1");
  if (!["1", "2"].includes(environment))
    throw new Error("Ambiente deve ser 1 ou 2.");
  if (environment !== "1")
    throw new Error(
      "Os endpoints desta PoC estao fixados em producao. Configure URLs oficiais de homologacao antes de utiliza-la.",
    );
  const company = option("--cnpj", parts.issuer),
    uf = option("--uf", parts.uf);
  if (!/^[0-9]{14}$/.test(company))
    throw new Error("CNPJ do interessado invalido.");
  const root = resolve(
    option(
      "--out",
      fileURLToPath(new URL("../../../runtime/sefaz-poc", import.meta.url)),
    ),
  );
  const folder = join(root, `${company}-${environment}`);
  await mkdir(folder, { recursive: true });
  const lockPath = join(folder, "consumer.lock");
  let lock;
  try {
    lock = await open(lockPath, "wx");
  } catch {
    throw new Error(
      "Existe outro consumidor ou uma trava de execucao anterior. Confira o processo antes de remover consumer.lock.",
    );
  }
  try {
    await lock.writeFile(
      JSON.stringify({
        pid: process.pid,
        started_at: new Date().toISOString(),
      }),
    );
    if (command === "status") {
      const xml = statusRequest(key, environment);
      const reply = await soap(
        svspUrl,
        "CTeConsultaV4/cteConsultaCT",
        xml,
        args.includes("--no-certificate"),
      );
      const data = reply.status === 200 ? result(reply.body, "status") : {};
      const evidence = {
        operation: command,
        timestamp: new Date().toISOString(),
        url: svspUrl,
        http_status: reply.status,
        cStat: data.cStat ?? null,
        xMotivo: data.xMotivo ?? null,
        complete_xml_recovered: false,
      };
      await atomic(join(folder, "status.request.xml"), xml);
      await atomic(join(folder, "status.response.xml"), reply.body);
      await atomic(
        join(folder, "status.result.json"),
        JSON.stringify(evidence, null, 2),
      );
      console.log(JSON.stringify(evidence));
      if (reply.status !== 200) process.exitCode = 2;
      return;
    }
    const stateFile = join(folder, "state.json");
    const state = await json(stateFile, {
      lastNsu: "000000000000000",
      nextRequestAt: 0,
    });
    if (Date.now() < state.nextRequestAt)
      throw new Error(
        `Aguarde ate ${new Date(state.nextRequestAt).toISOString()} para nova consulta de distribuicao.`,
      );
    const batches = Number(option("--max-batches", "1"));
    if (!Number.isInteger(batches) || batches < 1 || batches > 20)
      throw new Error("max-batches deve estar entre 1 e 20.");
    const pending = join(folder, "pending.json");
    const records: object[] = [];
    let targetRecovered = false;
    for (let batch = 0; batch < (command === "nsu" ? 1 : batches); batch++) {
      const nsu = command === "nsu" ? option("--nsu", "") : state.lastNsu;
      const xml = distributionRequest(
        company,
        uf,
        environment,
        nsu,
        command === "nsu",
      );
      let reply = await json(pending, {});
      if (!reply.body) {
        reply = {
          ...(await soap(
            distributionUrl,
            "CTeDistribuicaoDFe/cteDistDFeInteresse",
            xml,
          )),
          operation: command,
          inputNsu: nsu,
        };
        await atomic(pending, JSON.stringify(reply));
        await atomic(join(folder, "distribution.request.xml"), xml);
      } else if (reply.operation !== command || reply.inputNsu !== nsu)
        throw new Error(
          "Ha uma resposta pendente de processamento. Retome a mesma operacao e NSU.",
        );
      if (reply.status !== 200) {
        await atomic(
          join(folder, "distribution.result.json"),
          JSON.stringify(
            {
              operation: command,
              timestamp: new Date().toISOString(),
              url: distributionUrl,
              http_status: reply.status,
              cStat: null,
              complete_xml_recovered: false,
            },
            null,
            2,
          ),
        );
        await unlink(pending);
        throw new Error(
          `Distribuicao respondeu HTTP ${reply.status}. Confira o certificado e a autorizacao do interessado.`,
        );
      }
      const data = result(reply.body, "distribution"),
        docs = documents(data, key);
      if (
        command === "dist" &&
        data.cStat === "138" &&
        (!/^[0-9]{1,15}$/.test(String(data.ultNSU)) ||
          BigInt(String(data.ultNSU)) <= BigInt(nsu))
      )
        throw new Error(
          "Resposta de distribuicao sem avanco do NSU. Resposta preservada para verificacao local.",
        );
      let recovered = false;
      for (const doc of docs) {
        await atomic(join(folder, `NSU_${doc.nsu}.xml`), doc.xml);
        if (doc.complete && doc.targetMatches) {
          await atomic(join(folder, `CTE_${key}.xml`), doc.xml);
          recovered = true;
        }
      }
      const evidence = {
        operation: command,
        timestamp: new Date().toISOString(),
        url: distributionUrl,
        http_status: reply.status,
        cStat: data.cStat,
        xMotivo: data.xMotivo,
        input_nsu: nsu,
        ultNSU: data.ultNSU,
        maxNSU: data.maxNSU,
        document_count: docs.length,
        full_cte_count: docs.filter((doc) => doc.complete).length,
        complete_xml_recovered: recovered,
      };
      records.push(evidence);
      console.log(JSON.stringify(evidence));
      targetRecovered ||= recovered;
      if (
        command === "dist" &&
        data.ultNSU &&
        ["137", "138"].includes(String(data.cStat))
      )
        state.lastNsu = String(data.ultNSU);
      const exhausted =
        data.cStat === "137" ||
        data.cStat === "656" ||
        Boolean(data.ultNSU && data.ultNSU === data.maxNSU);
      if (exhausted) state.nextRequestAt = Date.now() + 3600000;
      await atomic(stateFile, JSON.stringify(state, null, 2));
      await atomic(
        join(folder, "distribution.result.json"),
        JSON.stringify(records, null, 2),
      );
      await unlink(pending);
      if (!["137", "138"].includes(String(data.cStat))) process.exitCode = 2;
      if (recovered || exhausted || data.cStat !== "138" || command === "nsu")
        break;
    }
    if (!targetRecovered && !process.exitCode) process.exitCode = 3;
  } finally {
    await lock.close();
    await unlink(lockPath);
  }
}
main().catch((error) => {
  console.error(
    error instanceof Error ? error.message : "Falha na consulta SEFAZ.",
  );
  process.exitCode = 2;
});
