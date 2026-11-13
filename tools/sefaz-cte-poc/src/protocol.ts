import { gunzipSync } from "node:zlib";
import { XMLParser, XMLValidator } from "fast-xml-parser";

export const namespace = "http://www.portalfiscal.inf.br/cte";
export const distributionUrl =
  "https://www1.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx";
export const svspUrl =
  "https://nfe.fazenda.sp.gov.br/CTeWS/WS/CTeConsultaV4.asmx";
type Xml = Record<string, unknown>;
export function node(value: unknown): Xml {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Xml)
    : {};
}
export function parseXml(xml: string): Xml {
  if (
    Buffer.byteLength(xml) > 20 * 1024 * 1024 ||
    /<!DOCTYPE|<!ENTITY/i.test(xml)
  )
    throw new Error("XML rejeitado por tamanho ou declaracao de entidades.");
  if (XMLValidator.validate(xml) !== true)
    throw new Error("Resposta XML invalida.");
  return new XMLParser({
    ignoreAttributes: false,
    attributeNamePrefix: "@",
    removeNSPrefix: true,
    parseTagValue: false,
    trimValues: true,
  }).parse(xml) as Xml;
}
export function keyParts(key: string) {
  if (!/^[0-9]{44}$/.test(key))
    throw new Error("A chave deve conter exatamente 44 digitos.");
  const sum = [...key.slice(0, 43)]
    .reverse()
    .reduce((sum, digit, index) => sum + Number(digit) * (2 + (index % 8)), 0);
  const remainder = sum % 11;
  if (Number(key[43]) !== (remainder < 2 ? 0 : 11 - remainder))
    throw new Error("Digito verificador da chave invalido.");
  if (key.slice(20, 22) !== "57")
    throw new Error("A chave informada deve ser do modelo 57.");
  return {
    uf: key.slice(0, 2),
    issuer: key.slice(6, 20),
    serie: key.slice(22, 25),
    number: key.slice(25, 34),
    emissionType: key[34],
  };
}
export function envelope(body: string): string {
  return `<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body>${body}</s:Body></s:Envelope>`;
}
export function statusRequest(key: string, environment: string) {
  const { uf, emissionType } = keyParts(key);
  if (!["26", "35", "16", "14"].includes(uf) || emissionType !== "1")
    throw new Error(
      "Esta PoC de consulta atende emissao normal na SVSP. Use o autorizador oficial da UF para outros casos.",
    );
  return envelope(
    `<cteDadosMsg xmlns="${namespace}/wsdl/CTeConsultaV4"><consSitCTe xmlns="${namespace}" versao="4.00"><tpAmb>${environment}</tpAmb><xServ>CONSULTAR</xServ><chCTe>${key}</chCTe></consSitCTe></cteDadosMsg>`,
  );
}
export function distributionRequest(
  company: string,
  uf: string,
  environment: string,
  nsu: string,
  single: boolean,
) {
  if (
    !/^[0-9]{14}$/.test(company) ||
    !/^[0-9]{2}$/.test(uf) ||
    !/^[0-9]{1,15}$/.test(nsu)
  )
    throw new Error("CNPJ, UF ou NSU invalidos.");
  const query = single
    ? `<consNSU><NSU>${nsu.padStart(15, "0")}</NSU></consNSU>`
    : `<distNSU><ultNSU>${nsu.padStart(15, "0")}</ultNSU></distNSU>`;
  return envelope(
    `<cteDistDFeInteresse xmlns="${namespace}/wsdl/CTeDistribuicaoDFe"><cteDadosMsg><distDFeInt xmlns="${namespace}" versao="1.00"><tpAmb>${environment}</tpAmb><cUFAutor>${uf}</cUFAutor><CNPJ>${company}</CNPJ>${query}</distDFeInt></cteDadosMsg></cteDistDFeInteresse>`,
  );
}
export function result(xml: string, kind: "distribution" | "status") {
  const root = parseXml(xml),
    body = node(node(root.Envelope).Body);
  if (body.Fault) throw new Error("O servico retornou SOAP Fault.");
  const response =
    kind === "distribution"
      ? node(node(body.cteDistDFeInteresseResponse).cteDistDFeInteresseResult)
      : node(body.cteConsultaCTResult);
  const data = node(
    response[kind === "distribution" ? "retDistDFeInt" : "retConsSitCTe"],
  );
  if (!data.cStat)
    throw new Error("Retorno SEFAZ esperado ausente na resposta.");
  return data;
}
export function documents(data: Xml, key: string) {
  const zipped = node(data.loteDistDFeInt).docZip;
  const list = Array.isArray(zipped) ? zipped : zipped ? [zipped] : [];
  if (list.length > 50)
    throw new Error("Lote excede o limite de 50 documentos.");
  return list.map((item) => {
    const value = node(item);
    const nsu = String(value["@NSU"] ?? "");
    if (!/^[0-9]{1,15}$/.test(nsu))
      throw new Error("NSU de documento invalido.");
    const xml = gunzipSync(
      Buffer.from(String(value["#text"] ?? ""), "base64"),
      { maxOutputLength: 10 * 1024 * 1024 },
    ).toString("utf8");
    const parsed = parseXml(xml),
      complete = node(parsed.cteProc);
    const info = node(node(complete.CTe).infCte),
      protocol = node(node(complete.protCTe).infProt);
    const matches =
      info["@Id"] === `CTe${key}` &&
      protocol.chCTe === key &&
      protocol.cStat === "100";
    return {
      nsu: nsu.padStart(15, "0"),
      schema: String(value["@schema"] ?? ""),
      xml,
      complete: Boolean(complete.CTe && complete.protCTe),
      targetMatches: matches,
      kind: complete.CTe
        ? "cteProc"
        : parsed.procEventoCTe
          ? "evento"
          : parsed.resCTe
            ? "resumo"
            : "outro",
    };
  });
}
