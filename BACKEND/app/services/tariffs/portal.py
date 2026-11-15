"""Use the same authenticated read request as the Novelis tariff screen."""

import asyncio
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

import httpx


class PortalError(RuntimeError):
    def __init__(self, message, code="portal", stage="consulta_portal"):
        super().__init__(message)
        self.code, self.stage = code, stage


async def read_request(client, method, path, **options):
    """Retry only the read request used by the screen; never repeat a login blindly."""
    for attempt in range(2):
        try:
            response = await client.request(method, path, timeout=90, **options)
            if response.status_code in {502, 503, 504} and attempt == 0:
                await asyncio.sleep(1)
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            raise PortalError(
                "Consulta do portal indisponível.",
                "timeout" if isinstance(exc, httpx.TimeoutException) else "network",
            ) from None
        except httpx.HTTPStatusError as exc:
            raise PortalError(
                "O portal recusou a consulta.", f"http_{exc.response.status_code}"
            ) from None


class Options(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values, self.select, self.option = {}, None, None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.select = attrs.get("name")
            if self.select in {"origem", "destino"}:
                self.values[self.select] = []
        elif tag == "option" and self.select in {"origem", "destino"}:
            self.option = {"value": attrs.get("value", ""), "label": ""}
            self.values[self.select].append(self.option)

    def handle_endtag(self, tag):
        if tag == "option":
            self.option = None
        if tag == "select":
            self.select, self.option = None, None

    def handle_data(self, data):
        if self.option is not None:
            self.option["label"] += data


async def collect(config):
    cfg = config.novelis()
    url = cfg.get("tarifarioUrl") or "https://novelis.wtmh.com.br/tarifa/tarifario"
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "novelis.wtmh.com.br"
        or parsed.username
        or parsed.port not in (None, 443)
    ):
        raise PortalError("Configure a URL HTTPS do tarifário oficial Novelis.")
    if not cfg.get("tarifarioUser") or not cfg.get("tarifarioPass"):
        raise PortalError("Configure as credenciais locais do tarifário Novelis.")
    async with httpx.AsyncClient(
        base_url="https://novelis.wtmh.com.br", timeout=30, follow_redirects=True
    ) as client:
        try:
            response = await client.get("/login")
            response.raise_for_status()
            headers = {"Referer": "https://novelis.wtmh.com.br/login", "X-Show-Menu": "true"}
            if csrf := client.cookies.get("XSRF-TOKEN"):
                headers["X-XSRF-TOKEN"] = unquote(csrf)
            response = await client.post(
                "/login",
                json={
                    "email": cfg["tarifarioUser"],
                    "password": cfg["tarifarioPass"],
                    "remember": False,
                },
                headers=headers,
                follow_redirects=False,
            )
            if response.status_code in (302, 303):
                target = response.url.join(response.headers.get("location", ""))
                if target.scheme != "https" or target.host != parsed.hostname:
                    raise PortalError("O login redirecionou para um endereço não autorizado.")
                response = await client.get(target)
            response.raise_for_status()
            if response.url.host != parsed.hostname or response.url.path == "/login":
                raise PortalError(
                    "O portal não confirmou o login. Verifique a conta e possíveis desafios de autenticação."
                )
            response = await client.get("/tarifa/tarifario")
            response.raise_for_status()
            parser = Options()
            parser.feed(response.text)
            if not parser.values.get("origem") or not parser.values.get("destino"):
                raise PortalError(
                    "O portal não disponibilizou os filtros do tarifário para esta conta."
                )
            fields = {
                key: ""
                for key in (
                    "tipo_veiculo_id",
                    "tipo_transporte_id",
                    "desc_operacao_id",
                    "ramo_id",
                    "grupo_empresa_id",
                    "origem_id",
                    "destino_id",
                    "valor_de",
                    "valor_ate",
                    "data_de",
                    "data_ate",
                    "periodo",
                )
            }
            response = await read_request(
                client,
                "POST",
                "/tarifa/get_tarifas/",
                data=fields,
                headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"},
            )
            response.raise_for_status()
            if response.url.path.rstrip("/") != "/tarifa/get_tarifas":
                raise PortalError("A sessão do tarifário expirou antes da consulta.")
            value = response.json()
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("data"), list)
                or any(not isinstance(row, dict) for row in value["data"])
            ):
                raise PortalError("O portal retornou um formato de tarifário não reconhecido.")
            if int(value.get("recordsTotal") or len(value["data"])) > len(value["data"]):
                raise PortalError(
                    "O portal retornou uma lista parcial de tarifas. A coleta foi interrompida."
                )
            return value["data"], parser.values
        except (httpx.HTTPError, ValueError, KeyError):
            # Do not forward response bodies, headers, cookies or credentials.
            raise PortalError(
                "Não foi possível consultar o tarifário. Verifique acesso ao portal e credenciais locais."
            ) from None
