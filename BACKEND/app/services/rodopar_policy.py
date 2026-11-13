"""Keep the legacy Rodopar implementation available behind an explicit switch."""

from urllib.parse import urlparse

from app.config.settings import Settings

LEGACY_RODOPAR_FLOWS = {"pre-passo", "integrado", "pdf-rodopar", "rodopar-pdf"}
DISABLED_MESSAGE = (
    "Acesso ao Rodopar desabilitado. O PDF utiliza consulta ao banco e Crystal Reports. "
    "O codigo legado foi preservado; sua reativacao exige RODOPAR_BROWSER_ENABLED=true."
)


def require_legacy_rodopar(config) -> None:
    if not config.bool("RODOPAR_BROWSER_ENABLED", False):
        raise RuntimeError(DISABLED_MESSAGE)


def rodopar_url_blocked(settings: Settings, url: str) -> bool:
    if settings.rodopar_browser_enabled:
        return False
    host = (urlparse(url).hostname or "").lower()
    configured = {
        (urlparse(value).hostname or "").lower()
        for value in (settings.pre_url, settings.pre_html5_url)
    }
    return bool(host and (host in configured or host == "datapardc.com" or host.endswith(".datapardc.com")))
