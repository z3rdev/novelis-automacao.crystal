import { test } from "node:test";
import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import {
  keyParts,
  envelope,
  result,
  documents,
  distributionRequest,
  parseXml,
} from "./protocol.js";

const key = "26261113254104001065570100000028791000028796";
test("chave real fornecida possui DV valido", () => {
  assert.equal(keyParts(key).number, "000002879");
  assert.throws(() => keyParts(key.slice(0, -1) + "0"), /verificador/);
});
test("consulta usa o status externo sem confundir o codigo de evento", () => {
  const xml = envelope(
    "<cteConsultaCTResult><retConsSitCTe><cStat>100</cStat><procEventoCTe><infEvento><cStat>135</cStat></infEvento></procEventoCTe></retConsSitCTe></cteConsultaCTResult>",
  );
  assert.equal(result(xml, "status").cStat, "100");
});
test("eventos gzip e resumos sao classificados separadamente do XML completo", () => {
  const data = {
    loteDistDFeInt: {
      docZip: {
        "@NSU": "1",
        "@schema": "procEventoCTe_v4.00.xsd",
        "#text": gzipSync(
          `<procEventoCTe><chCTe>${key}</chCTe></procEventoCTe>`,
        ).toString("base64"),
      },
    },
  };
  const [doc] = documents(data, key);
  assert.equal(doc.kind, "evento");
  assert.equal(doc.complete, false);
  assert.equal(doc.targetMatches, false);
});
test("rejeita entidades e informa o NSU exigido na consulta pontual", () => {
  assert.throws(
    () => parseXml('<!DOCTYPE x [<!ENTITY x "test">]><x/>'),
    /entidades/,
  );
  assert.throws(
    () => distributionRequest("13254104001065", "26", "1", "", true),
    /NSU/,
  );
  assert.match(
    distributionRequest("13254104001065", "26", "1", "123", true),
    /<consNSU><NSU>000000000000123/,
  );
});

test("XML completo precisa conter a chave procurada no documento e no protocolo", () => {
  for (const protocolKey of [key, "0".repeat(44)]) {
    const xml = `<cteProc><CTe><infCte Id="CTe${key}"/></CTe><protCTe><infProt><chCTe>${protocolKey}</chCTe><cStat>100</cStat></infProt></protCTe></cteProc>`;
    const [document] = documents(
      {
        loteDistDFeInt: {
          docZip: {
            "@NSU": "123",
            "#text": gzipSync(xml).toString("base64"),
          },
        },
      },
      key,
    );
    assert.equal(document.complete, true);
    assert.equal(document.targetMatches, protocolKey === key);
  }
});
