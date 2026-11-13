from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.services.crystal_reports.models import DacteRequest
from app.services.crystal_reports.service import CrystalReportError

NS = {"cte": "http://www.portalfiscal.inf.br/cte"}
MAX_XML_BYTES = 10 * 1024 * 1024


def validate_cte_xml(content: bytes, document: DacteRequest) -> str:
    if (
        len(content) > MAX_XML_BYTES
        or b"<!DOCTYPE" in content.upper()
        or b"<!ENTITY" in content.upper()
    ):
        raise CrystalReportError("XML excede o limite ou contem declaracoes nao permitidas.", 422)
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise CrystalReportError("Arquivo XML invalido.", 422) from exc
    info = root.find(".//cte:infCte", NS)
    protocol = root.find(".//cte:protCTe/cte:infProt", NS)
    if info is None or protocol is None:
        raise CrystalReportError(
            "Informe um XML CT-e processado com protocolo de autorizacao.", 422
        )
    if protocol.findtext("cte:cStat", namespaces=NS) != "100":
        raise CrystalReportError(
            "O protocolo arquivado no XML nao indica autorizacao do CT-e.", 422
        )
    if info.findtext("cte:ide/cte:mod", namespaces=NS) != "57":
        raise CrystalReportError("Esta rota suporta XML de CT-e modelo 57.", 422)
    number = info.findtext("cte:ide/cte:nCT", default="", namespaces=NS)
    serie = info.findtext("cte:ide/cte:serie", default="", namespaces=NS)
    if (
        not number.isascii()
        or not number.isdecimal()
        or not serie.isascii()
        or not serie.isdecimal()
        or int(number) != document.documento
        or serie != document.serie
    ):
        raise CrystalReportError("Serie/documento do XML nao correspondem ao CT-e solicitado.", 422)
    key = protocol.findtext("cte:chCTe", default="", namespaces=NS)
    if len(key) != 44 or not key.isascii() or not key.isdecimal() or info.get("Id") != "CTe" + key:
        raise CrystalReportError("Chave do CT-e inconsistente entre documento e protocolo.", 422)
    if int(key[22:25]) != int(serie) or int(key[25:34]) != document.documento:
        raise CrystalReportError("Chave do CT-e nao corresponde a serie/documento do XML.", 422)
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CrystalReportError("O XML do CT-e precisa estar em UTF-8.", 422) from exc


class XmlDacteService:
    def __init__(self, settings: Settings, config: LegacyConfig) -> None:
        self.settings = settings
        self.config = config

    def export(self, document: DacteRequest) -> Path:
        source_dir = Path(self.config.xml_sefaz()["downloadDir"])
        source = source_dir / f"CTE_{document.filial}-{document.serie}-{document.documento}.xml"
        try:
            if source.stat().st_size > MAX_XML_BYTES:
                raise CrystalReportError("XML excede o limite de 10 MB.", 422)
            content = source.read_bytes()
        except FileNotFoundError as exc:
            raise CrystalReportError(
                "XML deste CT-e nao encontrado na pasta XML_SEFAZ_DOWNLOAD_DIR.", 404
            ) from exc
        except OSError as exc:
            raise CrystalReportError(
                "Nao foi possivel ler a pasta de XMLs configurada.", 503
            ) from exc
        xml = validate_cte_xml(content, document)
        try:
            from brazilfiscalreport.dacte import Dacte
        except ImportError as exc:
            raise CrystalReportError(
                'Instale a dependencia opcional do backend: pip install ".[dacte]".', 503
            ) from exc
        output_dir = self.settings.storage_dir / "reports" / "dacte-xml"
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / (
            f"dacte-{document.filial}-{document.serie}-{document.documento}-xml-{uuid4().hex}.pdf"
        )
        try:
            pdf = Dacte(xml=xml)
            pdf.output(str(output))
            return output
        except Exception as exc:
            output.unlink(missing_ok=True)
            raise CrystalReportError(
                "Nao foi possivel renderizar este XML de CT-e em PDF.", 422
            ) from exc
