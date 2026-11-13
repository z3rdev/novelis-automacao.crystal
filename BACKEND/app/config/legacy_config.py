from pathlib import Path
from typing import Any

from app.config.env_catalog import read_env_file
from app.config.settings import Settings


def parse_bool(value: Any, fallback: bool = False) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return fallback
    if text in {"1", "true", "sim", "yes", "on"}:
        return True
    if text in {"0", "false", "nao", "não", "no", "off"}:
        return False
    return fallback


def parse_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def parse_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return fallback


class LegacyConfig:
    def __init__(self, settings: Settings) -> None:
        example = read_env_file(settings.backend_root / ".env.example")
        active = read_env_file(settings.backend_root / ".env")
        self.settings = settings
        self.values = {**example, **active}

    def get(self, key: str, fallback: str = "") -> str:
        return str(self.values.get(key, fallback))

    def bool(self, key: str, fallback: bool = False) -> bool:
        return parse_bool(self.values.get(key), fallback)

    def int(self, key: str, fallback: int = 0) -> int:
        return parse_int(self.values.get(key), fallback)

    def float(self, key: str, fallback: float = 0.0) -> float:
        return parse_float(self.values.get(key), fallback)

    def path(self, key: str, fallback: str = "") -> str:
        return self.get(key, fallback).strip()

    def pre(self) -> dict[str, Any]:
        return {
            "rodoparBrowserEnabled": self.bool("RODOPAR_BROWSER_ENABLED", False),
            "url": self.get("PRE_URL", self.settings.pre_url),
            "html5Url": self.get("PRE_HTML5_URL", self.settings.pre_html5_url),
            "navigationTimeoutMs": self.int(
                "PRE_NAVIGATION_TIMEOUT_MS",
                self.int("BROWSER_NAVIGATION_TIMEOUT_MS", 45_000),
            ),
            "navigationRetries": self.int("PRE_NAVIGATION_RETRIES", 3),
            "user": self.get("PRE_USER"),
            "pass": self.get("PRE_PASS"),
            "manualLogin": self.bool("PRE_MANUAL_LOGIN"),
            "manualLoginOnly": self.bool("PRE_MANUAL_LOGIN_ONLY"),
            "dellmarManualLogin": self.bool("PRE_DELLMAR_MANUAL_LOGIN"),
            "dellmarUser": self.get("PRE_DELLMAR_USER"),
            "dellmarPass": self.get("PRE_DELLMAR_PASS"),
            "captureFile": self.path("PRE_CAPTURE_FILE", "captures/pre-pointer-map.json"),
            "replaySteps": self.int("PRE_REPLAY_STEPS", 3),
            "stepDelayMs": self.int("PRE_STEP_DELAY_MS", self.settings.pre_step_delay_ms),
            "replayFromCapture": self.bool("PRE_REPLAY_FROM_CAPTURE", True),
            "replayContinueAfterTarifario": self.bool("PRE_REPLAY_CONTINUE_AFTER_TARIFARIO", True),
            "replayContinueFromStep": self.int("PRE_REPLAY_CONTINUE_FROM_STEP", 0),
            "replayContinueSteps": self.int("PRE_REPLAY_CONTINUE_STEPS", 0),
            "fillFilialFromSheet": self.bool("PRE_FILL_FILIAL_FROM_SHEET", True),
            "fillDocumentoFromSheet": self.bool("PRE_FILL_DOCUMENTO_FROM_SHEET", True),
            "filialStepNumber": self.int("PRE_FILIAL_STEP_NUMBER", 9),
            "documentoStepNumber": self.int("PRE_DOCUMENTO_STEP_NUMBER", 10),
            "filialRowIndex": self.int("PRE_FILIAL_ROW_INDEX", 0),
            "documentoRowIndex": self.int("PRE_DOCUMENTO_ROW_INDEX", 0),
            "downloadFromStep": self.int("PRE_DOWNLOAD_FROM_STEP", 25),
            "handleDownloadsAfterStep": self.bool("PRE_HANDLE_DOWNLOADS_AFTER_STEP", True),
            "downloadSourceDir": self.path(
                "PRE_DOWNLOAD_SOURCE_DIR",
                self.get("BROWSER_DOWNLOADS_DIR", "captures/downloads"),
            ),
            "downloadWaitMs": self.int("PRE_DOWNLOAD_WAIT_MS", 12_000),
            "sessionStateFile": self.path("SESSION_STATE_FILE", "captures/session-state.json"),
            "saveSessionState": self.bool("SESSION_SAVE", True),
            "reuseSessionFirst": self.bool("PRE_REUSE_SESSION_FIRST", True),
            "saveDebugShots": self.bool("PRE_SAVE_DEBUG_SHOTS", True),
            "debugDir": self.path("PRE_DEBUG_DIR", "captures/debug"),
            "bringToFront": self.bool("PRE_BRING_TO_FRONT", False),
            "consultaFile": self.path("PRE_CONSULTA_FILE", "FONTE DE DADOS/CONSULTA.xlsx"),
            "consultaSheet": self.get("PRE_CONSULTA_SHEET"),
            "consultaStartRow": self.int("PRE_CONSULTA_START_ROW", 2),
        }

    def novelis(self) -> dict[str, Any]:
        return {
            "loginUrl": self.get("NOVELIS_LOGIN_URL") or "https://novelis.wtmh.com.br/login",
            "portalUrl": self.get("NOVELIS_PORTAL_URL") or "https://novelis.wtmh.com.br/portal",
            "dashboardUrl": self.get("NOVELIS_DASHBOARD_URL") or "https://novelis.wtmh.com.br/portal/dashboard",
            "chamadoEntradaUrl": self.get("NOVELIS_CHAMADO_ENTRADA_URL")
            or "https://novelis.wtmh.com.br/portal/workflow/entrada",
            "chamadoDiretoUrl": self.get("NOVELIS_CHAMADO_DIRETO_URL")
            or "https://novelis.wtmh.com.br/portal/chamado/",
            "chamadoPreferDirectUrl": self.bool("NOVELIS_CHAMADO_PREFER_DIRECT_URL", True),
            "chamadoWorkflowFallback": self.bool("NOVELIS_CHAMADO_WORKFLOW_FALLBACK", False),
            "listaUrl": self.get("NOVELIS_LISTA_URL") or "https://novelis.wtmh.com.br/portal/workflow/saida",
            "user": self.get("NOVELIS_USER"),
            "pass": self.get("NOVELIS_PASS"),
            "directChamadoMode": self.bool("NOVELIS_DIRECT_CHAMADO_MODE"),
            "enableTarifarioStep": self.bool("NOVELIS_ENABLE_TARIFARIO", True),
            "openChamadoAfterTarifario": self.bool("NOVELIS_OPEN_CHAMADO_AFTER_TARIFARIO"),
            "tarifarioNewTab": self.bool("NOVELIS_TARIFARIO_NEW_TAB", True),
            "tarifarioKeepTabOpen": self.bool("NOVELIS_TARIFARIO_KEEP_TAB_OPEN", True),
            "tarifarioUrl": self.get("NOVELIS_TARIFARIO_URL"),
            "tarifarioUser": self.get("NOVELIS_TARIFARIO_USER") or self.get("NOVELIS_USER"),
            "tarifarioPass": self.get("NOVELIS_TARIFARIO_PASS") or self.get("NOVELIS_PASS"),
            "consultaFile": self.path("NOVELIS_CONSULTA_FILE", "FONTE DE DADOS/CONSULTA.xlsx"),
            "consultaSheet": self.get("NOVELIS_CONSULTA_SHEET"),
            "consultaStartRow": self.int("NOVELIS_CONSULTA_START_ROW", 2),
            "onlySelectedDocumento": self.bool("NOVELIS_ONLY_SELECTED_DOCUMENTO", True),
            "documentoRowIndex": self.int("NOVELIS_DOCUMENTO_ROW_INDEX", 0),
            "documentoFilter": self.get("NOVELIS_DOCUMENTO_FILTER"),
            "valorCompareTolerance": self.float("NOVELIS_VALOR_COMPARE_TOLERANCE", 0.05),
            "afterSearchWaitMs": self.int("NOVELIS_TARIFARIO_AFTER_SEARCH_WAIT_MS", 1200),
            "tarifarioOutputFile": self.path("NOVELIS_TARIFARIO_OUTPUT_FILE", "captures/tarifario-resultados.json"),
            "tonTempFile": self.path("NOVELIS_TON_TEMP_FILE", "captures/ton-temp.json"),
            "chamadoItem": self.get("NOVELIS_CHAMADO_ITEM", "AF.001 - Auditoria de Frete"),
            "chamadoTitulo": self.get("NOVELIS_CHAMADO_TITULO"),
            "chamadoAssinatura": self.get("NOVELIS_CHAMADO_ASSINATURA"),
            "chamadoUploadFromTarifario": self.bool("NOVELIS_CHAMADO_UPLOAD_FROM_TARIFARIO", True),
            "chamadoUploadRetryAttempts": self.int("NOVELIS_CHAMADO_UPLOAD_RETRY_ATTEMPTS", 1),
            "chamadoUploadRetryDelayMs": self.int("NOVELIS_CHAMADO_UPLOAD_RETRY_DELAY_MS", 1500),
            "chamadoDownloadTargetDir": self.path(
                "NOVELIS_CHAMADO_DOWNLOAD_TARGET_DIR",
                "captures/tarifario-downloads",
            ),
            "chamadoZipDir": self.path(
                "NOVELIS_CHAMADO_ZIP_DIR",
                r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\ZIPS-NOVELIS",
            ),
            "chamadoPdfSourceDir": self.path(
                "RODOPAR_PDF_DOWNLOAD_TARGET_DIR",
                r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\PDFS-RODOPAR",
            ),
            "chamadoXmlSourceDir": self.path(
                "XML_SEFAZ_DOWNLOAD_DIR",
                r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\XML-SEFAZ",
            ),
            "chamadoSalvar": self.bool("NOVELIS_CHAMADO_SALVAR", True),
            "chamadoClosePage": self.bool("NOVELIS_CHAMADO_CLOSE_PAGE", False),
            "listaScrapeEnabled": self.bool("NOVELIS_LISTA_SCRAPE_ENABLED", True),
            "jdaValidationEnabled": self.bool("NOVELIS_JDA_VALIDATION_ENABLED"),
            "relatorioCteXmlEnabled": self.bool("NOVELIS_RELATORIO_CTE_XML_ENABLED", True),
            "relatorioCteXmlUrl": self.get(
                "NOVELIS_RELATORIO_CTE_XML_URL",
                "https://novelis.wtmh.com.br/custom/relatorio_cte_xml",
            ),
            "relatorioCteXmlExcelFile": self.path(
                "NOVELIS_RELATORIO_CTE_XML_EXCEL_FILE",
                r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\FONTE-DADOS\RELATORIO-NOVELIS\relatorio_cte.xlsx",
            ),
            "relatorioCteXmlJsonFile": self.path(
                "NOVELIS_RELATORIO_CTE_XML_JSON_FILE",
                r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\FONTE-DADOS\RELATORIO-NOVELIS\relatorio_cte.json",
            ),
            "relatorioCteXmlDownloadTimeoutMs": self.int(
                "NOVELIS_RELATORIO_CTE_XML_DOWNLOAD_TIMEOUT_MS",
                120_000,
            ),
            "relatorioCteXmlDateStart": self.get("NOVELIS_RELATORIO_CTE_XML_DATE_START", "2025-01-01"),
            "relatorioCteXmlSkipIfFreshToday": self.bool(
                "NOVELIS_RELATORIO_CTE_XML_SKIP_IF_FRESH_TODAY",
                True,
            ),
            "chamadosLogFile": self.path(
                "NOVELIS_CHAMADOS_LOG_FILE",
                r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\FONTE-DADOS\CHAMADOS-PROCESSADOS\chamados-processados.json",
            ),
            "chamadosSnapshotFile": self.path(
                "NOVELIS_CHAMADOS_SNAPSHOT_FILE",
                r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\.REGISTRO\NOVELIS-STATUS\chamados-novelis-atual.json",
            ),
        }

    def gnre(self) -> dict[str, Any]:
        return {
            "enabled": self.bool("GNRE_ENABLED", True),
            "url": self.get("GNRE_URL"),
            "user": self.get("GNRE_USER"),
            "pass": self.get("GNRE_PASS"),
            "outputDir": self.path("GNRE_OUTPUT_DIR", "captures/gnre"),
        }

    def consulta_db(self) -> dict[str, Any]:
        return {
            "enabled": self.bool("CONSULTA_DB_FALLBACK_ENABLED", False),
            "server": self.get("CONSULTA_DB_SERVER") or self._consulta_db_server_from_parts(),
            "user": self.get("CONSULTA_DB_USER"),
            "pass": self.get("CONSULTA_DB_PASS"),
            "database": self.get("CONSULTA_DB_DATABASE", "db_visual_dellmar"),
            "pagGrupoClienteCod": self.int("CONSULTA_DB_PAG_GRUPO_CLIENTE_COD", 3),
            "encrypt": self.bool("CONSULTA_DB_ENCRYPT", False),
            "trustServerCertificate": self.bool("CONSULTA_DB_TRUST_SERVER_CERTIFICATE", True),
            "connectionTimeoutMs": self.int("CONSULTA_DB_CONNECTION_TIMEOUT_MS", 15_000),
            "requestTimeoutMs": self.int("CONSULTA_DB_REQUEST_TIMEOUT_MS", 120_000),
        }

    def _consulta_db_server_from_parts(self) -> str:
        host = self.get("CONSULTA_DB_HOST").strip()
        port = self.get("CONSULTA_DB_PORT").strip()
        if host and port:
            return f"{host},{port}"
        return host

    def rodopar_pdf(self) -> dict[str, Any]:
        return {
            **self.pre(),
            "ctes": self.get("RODOPAR_PDF_DOWNLOAD_CTES"),
            "defaultFilial": self.get("RODOPAR_PDF_DEFAULT_FILIAL"),
            "defaultSerie": self.get("RODOPAR_PDF_DEFAULT_SERIE", "10"),
            "downloadTargetDir": self.path(
                "RODOPAR_PDF_DOWNLOAD_TARGET_DIR",
                r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\PDFS-RODOPAR",
            ),
            "downloadSourceDir": self.path(
                "RODOPAR_PDF_DOWNLOAD_SOURCE_DIR",
                self.path("PRE_DOWNLOAD_SOURCE_DIR", self.get("BROWSER_DOWNLOADS_DIR", "captures/downloads")),
            ),
            "extraDownloadDirs": self.get("RODOPAR_PDF_EXTRA_DOWNLOAD_DIRS", ""),
            "downloadWaitMs": self.int("RODOPAR_PDF_DOWNLOAD_WAIT_MS", self.int("PRE_DOWNLOAD_WAIT_MS", 60_000)),
            "renameDownloadsToCte": self.bool(
                "RODOPAR_PDF_RENAME_DOWNLOADS_TO_CTE",
                self.bool("RODOPAR_PDF_RENAME_DOWNLOADS_TO_CTRC", True),
            ),
            "captureFile": self.path(
                "RODOPAR_PDF_DOWNLOAD_CAPTURE_FILE",
                "captures/rodopar-download-pdfs-pointer-map.json",
            ),
            "firstStartStep": self.int("RODOPAR_PDF_FIRST_START_STEP", 1),
            "loopStartStep": self.int("RODOPAR_PDF_LOOP_START_STEP", 0),
            "loopEndStep": self.int("RODOPAR_PDF_LOOP_END_STEP", 0),
            "stepDelayMs": self.int("RODOPAR_PDF_STEP_DELAY_MS", 3000),
            "inputStepDelayMs": self.int("RODOPAR_PDF_INPUT_STEP_DELAY_MS", 3000),
            "sensitiveStepDelayMs": self.int("RODOPAR_PDF_SENSITIVE_STEP_DELAY_MS", 4500),
            "replayOverlayEnabled": self.bool("RODOPAR_PDF_REPLAY_OVERLAY_ENABLED", True),
            "readConsulta": self.bool("RODOPAR_PDF_READ_CONSULTA", True),
            "reuseSessionFirst": self.bool("RODOPAR_PDF_REUSE_SESSION_FIRST", False),
            "rodoparManualLoginWait": self.bool("RODOPAR_PDF_WAIT_MANUAL_LOGIN", True),
            "rodoparManualLoginTimeoutSec": self.int("RODOPAR_PDF_MANUAL_LOGIN_TIMEOUT_SEC", 900),
            "consultaFile": self.path(
                "RODOPAR_PDF_CONSULTA_FILE",
                self.path("PRE_CONSULTA_FILE", "FONTE DE DADOS/CONSULTA.xlsx"),
            ),
            "consultaSheet": self.get("RODOPAR_PDF_CONSULTA_SHEET")
            or self.get("PRE_CONSULTA_SHEET"),
            "consultaStartRow": self.int(
                "RODOPAR_PDF_CONSULTA_START_ROW",
                self.int("PRE_CONSULTA_START_ROW", 2),
            ),
        }

    def pendentes(self) -> dict[str, Any]:
        return {
            "outputFile": self.path("PENDENTES_OUTPUT_FILE", "captures/pendentes/latest-python.json"),
            "sourceJson": self.path("PENDENTES_SOURCE_JSON", "captures/pendentes-comandos/latest-enriched.json"),
            "skipRodopar": self.bool("PENDENTES_SKIP_RODOPAR", False),
            "skipPdf": self.bool("PENDENTES_SKIP_PDF", False),
            "pdfSource": self.get("PENDENTES_PDF_SOURCE", "crystal").strip().lower(),
            "skipXml": self.bool("PENDENTES_SKIP_XML", False),
            "skipComprovantes": self.bool("PENDENTES_SKIP_COMPROVANTES", False),
            "skipNovelis": self.bool("PENDENTES_SKIP_NOVELIS", False),
            "stopOnError": self.bool("PENDENTES_STOP_ON_ERROR", False),
            "refreshNovelisRelatorio": self.bool("PENDENTES_REFRESH_NOVELIS_RELATORIO", True),
            "refreshNovelisRelatorioAfterChamados": self.bool("PENDENTES_REFRESH_NOVELIS_RELATORIO_AFTER_CHAMADOS", True),
            "strictNovelisRelatorio": self.bool("PENDENTES_STRICT_NOVELIS_RELATORIO", False),
            "requireNovelisFilterBeforeExecution": self.bool(
                "PENDENTES_REQUIRE_NOVELIS_FILTER_BEFORE_EXECUTION",
                True,
            ),
            "filteredSourceJson": self.path(
                "PENDENTES_FILTERED_SOURCE_JSON",
                "captures/pendentes/novelis-filtered.json",
            ),
            "refreshSql": self.bool("PENDENTES_REFRESH_SQL", True),
            "strictSql": self.bool("PENDENTES_STRICT_SQL", False),
            "sqlSourceJson": self.path(
                "PENDENTES_SQL_SOURCE_JSON",
                "captures/pendentes/sql-ultimos-5-dias.json",
            ),
        }

    def xml_sefaz(self) -> dict[str, Any]:
        return {
            "certificateCnpj": self.get("XML_SEFAZ_CERTIFICATE_CNPJ"),
            "certificateThumbprint": self.get("XML_SEFAZ_CERTIFICATE_THUMBPRINT"),
            "url": self.get(
                "XML_SEFAZ_URL",
                "https://www.cte.fazenda.gov.br/portal/consultaRecaptcha.aspx?tipoConsulta=completa&tipoConteudo=mCK/KoCqru0=",
            ),
            "ctes": self.get("XML_SEFAZ_CTES"),
            "defaultSerie": self.get("XML_SEFAZ_DEFAULT_SERIE", self.get("RODOPAR_PDF_DEFAULT_SERIE", "10")),
            "downloadDir": self.path(
                "XML_SEFAZ_DOWNLOAD_DIR",
                r"\\192.168.254.250\rede\Publico\AUTOMAÇÃO-CTE\XML-SEFAZ",
            ),
            "sourceJson": self.path("XML_SEFAZ_SOURCE_JSON"),
        }

    def comprovante_local(self) -> dict[str, Any]:
        return {
            "defaultFilial": self.get("COMPROVANTE_DEFAULT_FILIAL"),
            "defaultSerie": self.get("COMPROVANTE_DEFAULT_SERIE", "10"),
            "sourceDir": self.path(
                "COMPROVANTE_SOURCE_DIR",
                self.path("PRE_ZIP_EXTRA_COMPROVANTES_DIR", r"\\192.168.254.250\rede\Publico\EXPEDIÇÃO - COMPROVANTES"),
            ),
            "targetDir": self.path(
                "COMPROVANTE_TARGET_DIR",
                self.path("NOVELIS_CHAMADO_DOWNLOAD_TARGET_DIR", "captures/tarifario-downloads"),
            ),
            "prefixes": self.get(
                "COMPROVANTE_PREFIXES",
                self.get("PRE_ZIP_EXTRA_COMPROVANTES_PREFIXES", "GNR,CMP"),
            ),
            "zipPrefixes": self.get(
                "COMPROVANTE_ZIP_PREFIXES",
                self.get("COMPROVANTE_PREFIXES", self.get("PRE_ZIP_EXTRA_COMPROVANTES_PREFIXES", "GNR,CMP")),
            ),
            "resultFile": self.path(
                "COMPROVANTE_RESULT_FILE",
                self.path("NOVELIS_TARIFARIO_OUTPUT_FILE", "captures/tarifario-resultados.json"),
            ),
            "outputFile": self.path("COMPROVANTE_OUTPUT_FILE", "captures/comprovantes-local.json"),
            "consultaFile": self.path(
                "COMPROVANTE_CONSULTA_FILE",
                self.path("PRE_CONSULTA_FILE", "FONTE DE DADOS/CONSULTA.xlsx"),
            ),
            "consultaSheet": self.get("COMPROVANTE_CONSULTA_SHEET") or self.get("PRE_CONSULTA_SHEET"),
            "consultaStartRow": self.int(
                "COMPROVANTE_CONSULTA_START_ROW",
                self.int("PRE_CONSULTA_START_ROW", 2),
            ),
        }

    def chamado_novelis(self) -> dict[str, Any]:
        return {
            **self.novelis(),
            "ctes": self.get("CHAMADO_NOVELIS_CTES"),
            "defaultSerie": self.get("CHAMADO_NOVELIS_DEFAULT_SERIE", "10"),
            "sourceJson": self.path("CHAMADO_NOVELIS_SOURCE_JSON"),
            "tarifarioJson": self.path(
                "CHAMADO_NOVELIS_TARIFARIO_JSON",
                self.path("NOVELIS_TARIFARIO_OUTPUT_FILE", "captures/tarifario-resultados.json"),
            ),
            "outputDir": self.path("CHAMADO_NOVELIS_OUTPUT_DIR", "captures/novelis-chamados-direto"),
        }

    def cwd(self) -> Path:
        return self.settings.backend_root.parent
