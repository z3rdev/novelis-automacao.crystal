import https from "node:https";
import { readFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { spawn } from "node:child_process";
import { namespace } from "./protocol.js";

export async function soap(
  url: string,
  action: string,
  xml: string,
  noCertificate = false,
): Promise<{ status: number; body: string }> {
  const thumbprint = process.env.CTE_WINDOWS_CERT_THUMBPRINT;
  if (thumbprint && !noCertificate)
    return windowsSoap(url, action, xml, thumbprint);
  let pfx: Buffer | undefined;
  if (!noCertificate) {
    if (!process.env.CTE_A1_PFX)
      throw new Error(
        "Configure o A1 local ou o certificado instalado no Windows.",
      );
    pfx = await readFile(process.env.CTE_A1_PFX);
  }
  return new Promise((resolve, reject) => {
    const request = https.request(
      url,
      {
        method: "POST",
        pfx,
        passphrase: process.env.CTE_A1_PASSWORD,
        minVersion: "TLSv1.2",
        rejectUnauthorized: true,
        timeout: 30000,
        headers: {
          "Content-Type": `application/soap+xml; charset=utf-8; action="${namespace}/wsdl/${action}"`,
          "Content-Length": Buffer.byteLength(xml),
        },
      },
      (response) => {
        const chunks: Buffer[] = [];
        let bytes = 0;
        response.on("data", (chunk: Buffer) => {
          bytes += chunk.length;
          if (bytes > 20 * 1024 * 1024)
            request.destroy(new Error("response_limit"));
          else chunks.push(chunk);
        });
        response.on("end", () =>
          resolve({
            status: response.statusCode ?? 0,
            body: Buffer.concat(chunks).toString("utf8"),
          }),
        );
        response.on("error", () =>
          reject(new Error("Falha durante a leitura da resposta HTTPS.")),
        );
      },
    );
    request.on("timeout", () => request.destroy(new Error("timeout")));
    request.on("error", (error: NodeJS.ErrnoException) =>
      reject(
        new Error(`Falha TLS/HTTPS (${error.code ?? "transport_error"}).`),
      ),
    );
    request.end(xml);
  });
}

async function windowsSoap(
  url: string,
  action: string,
  xml: string,
  thumbprint: string,
) {
  if (process.platform !== "win32" || !/^[A-Fa-f0-9]{40}$/.test(thumbprint))
    throw new Error("Impressao digital Windows invalida.");
  const folder = await mkdtemp(join(tmpdir(), "novelis-sefaz-"));
  const output = join(folder, "response.xml");
  try {
    const status = await new Promise<string>((resolve, reject) => {
      const child = spawn(
        "curl.exe",
        [
          "--no-ssl-auto-client-cert",
          "--cert",
          `CurrentUser\\MY\\${thumbprint}`,
          "--connect-timeout",
          "15",
          "--max-time",
          "35",
          "--silent",
          "--show-error",
          "--max-filesize",
          "20971520",
          "--header",
          `Content-Type: application/soap+xml; charset=utf-8; action="${namespace}/wsdl/${action}"`,
          "--data-binary",
          "@-",
          "--output",
          output,
          "--write-out",
          "%{http_code}",
          url,
        ],
        { windowsHide: true },
      );
      let stdout = "";
      child.stdout.on("data", (data) => {
        stdout += data.toString();
      });
      child.stderr.resume(); // Native errors can contain certificate identifiers.
      child.on("error", () => reject(new Error("curl Schannel indisponivel.")));
      child.on("close", (code) =>
        code === 0
          ? resolve(stdout)
          : reject(new Error(`Falha curl/Schannel (codigo ${code}).`)),
      );
      child.stdin.on("error", () => undefined);
      child.stdin.end(xml);
    });
    return { status: Number(status), body: await readFile(output, "utf8") };
  } finally {
    if (dirname(resolve(folder)) !== resolve(tmpdir()))
      throw new Error("Diretorio temporario inesperado.");
    await rm(folder, { recursive: true, force: true });
  }
}
