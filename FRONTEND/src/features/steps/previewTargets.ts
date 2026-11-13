export const FAZENDA_URL =
  "https://www.cte.fazenda.gov.br/portal/consultaRecaptcha.aspx?tipoConsulta=completa&tipoConteudo=mCK/KoCqru0=";

export const NOVELIS_LOGIN_URL = "https://novelis.wtmh.com.br/login";

export const SEFAZ_CHAVE_SELECTOR = "#ctl00_ContentPlaceHolder1_txtChaveAcessoResumo";

export function previewTargetForFlow(flowKey: string | undefined, loginTarget: string) {
  const normalized = String(flowKey || "").toLowerCase();
  if (normalized === "xml-sefaz") return FAZENDA_URL;
  if (normalized === "chamado-novelis") return NOVELIS_LOGIN_URL;
  if (normalized === "comprovante-local") return "";
  return loginTarget;
}
