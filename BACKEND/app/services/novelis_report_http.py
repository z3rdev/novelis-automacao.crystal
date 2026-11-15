"""Authenticated, read-only Excel export used by the portal's own #excel button."""

import re
import unicodedata
from contextlib import AsyncExitStack, asynccontextmanager
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

import httpx
from openpyxl import load_workbook

ORIGIN = "https://novelis.wtmh.com.br"
REPORT = "/custom/relatorio_cte_xml"
EXPORT = "/custom/relatorio_cte_xml_excel"


class ReportDownloadError(RuntimeError):
    pass


class Fields(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside, self.fields, self.dates = False, {}, set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.inside = attrs.get("id") == "form"
        if self.inside and tag == "input" and attrs.get("name"):
            name = attrs["name"]
            if attrs.get("type", "text").lower() == "hidden":
                self.fields[name] = attrs.get("value", "")
            if name in {"de", "ate"}:
                self.dates.add(name)

    def handle_endtag(self, tag):
        if tag == "form":
            self.inside = False


def validate_workbook(path):
    def header(value):
        value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
        return re.sub(r"[^A-Z0-9_]", "", value.upper())

    with path.open("rb") as stream:
        book = load_workbook(stream, read_only=True, data_only=True)
        try:
            valid = any(
                any(
                    set(map(header, row)) & {"ID", "CTE_ID", "CTEID", "ID_CTE"}
                    and "SERIE" in set(map(header, row))
                    and set(map(header, row)) & {"NCT", "N_CT", "NUMERO", "DOCUMENTO", "NROCTE"}
                    for row in sheet.iter_rows(min_row=1, max_row=25, values_only=True)
                )
                for sheet in book
            )
            if not valid:
                raise ReportDownloadError(
                    "O Excel retornado não contém o cabeçalho esperado do relatório CT-e."
                )
        finally:
            book.close()


@asynccontextmanager
async def authenticated(config, transport=None):
    if not config.get("user") or not config.get("pass"):
        raise ReportDownloadError("Configure a conta do portal Novelis no backend.")
    async with httpx.AsyncClient(
        base_url=ORIGIN, timeout=30, follow_redirects=False, transport=transport
    ) as client:
        response = await client.get("/login")
        response.raise_for_status()
        headers = {"Referer": ORIGIN + "/login", "X-Show-Menu": "true"}
        if csrf := client.cookies.get("XSRF-TOKEN"):
            headers["X-XSRF-TOKEN"] = unquote(csrf)
        response = await client.post(
            "/login",
            json={"email": config["user"], "password": config["pass"], "remember": False},
            headers=headers,
        )
        if response.status_code not in {200, 302, 303}:
            raise ReportDownloadError("O portal não confirmou a autenticação do relatório.")
        target = response.headers.get("location", "")
        if target:
            parsed = urlsplit(str(response.url.join(target)))
            if (
                parsed.scheme != "https"
                or parsed.netloc != "novelis.wtmh.com.br"
                or parsed.path == "/login"
            ):
                raise ReportDownloadError("O portal não confirmou a autenticação do relatório.")
        yield client


async def download_report(config, date_range, output: Path, *, transport=None, client=None):
    """Never follow an export/login redirect or replace the previous file with HTML."""
    url = config.get("relatorioCteXmlUrl") or ORIGIN + REPORT
    if urlsplit(url)._replace(query="", fragment="").geturl() != ORIGIN + REPORT:
        raise ReportDownloadError("A exportação HTTP exige a URL oficial do relatório Novelis.")
    temporary = output.with_name(output.name + "." + uuid4().hex + ".tmp")
    try:
        async with AsyncExitStack() as stack:
            if client is None:
                client = await stack.enter_async_context(authenticated(config, transport))
            response = await client.get(REPORT)
            response.raise_for_status()
            form = Fields()
            form.feed(response.text)
            if form.dates != {"de", "ate"}:
                raise ReportDownloadError(
                    "Sessão ou formulário de exportação Novelis indisponível."
                )
            fields = {
                **form.fields,
                "de": date_range["startBR"],
                "ate": date_range["endBR"],
                "tipo": "date",
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            async with client.stream(
                "POST",
                EXPORT,
                data=fields,
                headers={"Referer": ORIGIN + REPORT},
                timeout=max(
                    30, int(config.get("relatorioCteXmlDownloadTimeoutMs") or 120000) / 1000
                ),
            ) as response:
                if response.status_code != 200:
                    raise ReportDownloadError("O portal não entregou o Excel autenticado.")
                size = 0
                with temporary.open("wb") as stream:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 50 * 1024 * 1024:
                            raise ReportDownloadError("O Excel excedeu o limite de 50 MB.")
                        stream.write(chunk)
            with ZipFile(temporary) as archive:
                if "xl/workbook.xml" not in archive.namelist():
                    raise ReportDownloadError("O portal não retornou uma planilha Excel válida.")
            validate_workbook(temporary)
            temporary.replace(output)
        return {
            "file": output,
            "suggestedName": output.name,
            "sourceUrl": ORIGIN + REPORT,
            "dateRange": date_range,
            "transport": "http",
        }
    except ReportDownloadError:
        raise
    except (httpx.HTTPError, BadZipFile, OSError, ValueError):
        raise ReportDownloadError(
            "Não foi possível obter o Excel Novelis por HTTP autenticado."
        ) from None
    finally:
        temporary.unlink(missing_ok=True)
