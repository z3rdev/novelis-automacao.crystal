import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.services.tariffs import portal


def test_collector_uses_only_login_and_the_portal_read_endpoints(monkeypatch):
    calls = []

    async def reply(request):
        path = request.url.path
        calls.append((request.method, path))
        if path == "/login" and request.method == "GET":
            return httpx.Response(200, headers={"set-cookie": "XSRF-TOKEN=fixture%3D; Path=/"})
        if path == "/login":
            assert json.loads(request.content)["password"] == "fixture-private"
            assert request.headers["X-XSRF-TOKEN"] == "fixture="
            return httpx.Response(303, headers={"location": "/portal/dashboard"})
        if path == "/tarifa/tarifario":
            return httpx.Response(
                200,
                text='<select name="origem"><option value="1112">ES-Cariacica</option></select><select name="destino"><option value="123">PB-Cabedelo</option></select>',
            )
        if path == "/tarifa/get_tarifas/":
            assert b"origem_id=&destino_id=" in request.content
            return httpx.Response(200, json={"data": [{"id": "1", "rota_id": "2"}]})
        return httpx.Response(200)

    cls = httpx.AsyncClient
    monkeypatch.setattr(
        portal.httpx, "AsyncClient", lambda **kw: cls(**kw, transport=httpx.MockTransport(reply))
    )
    config = SimpleNamespace(
        novelis=lambda: {
            "tarifarioUrl": "https://novelis.wtmh.com.br/tarifa/tarifario",
            "tarifarioUser": "fixture",
            "tarifarioPass": "fixture-private",
        }
    )
    rows, options = asyncio.run(portal.collect(config))
    assert len(rows) == 1 and options["destino"][0]["label"] == "PB-Cabedelo"
    assert calls == [
        ("GET", "/login"),
        ("POST", "/login"),
        ("GET", "/portal/dashboard"),
        ("GET", "/tarifa/tarifario"),
        ("POST", "/tarifa/get_tarifas/"),
    ]


def test_credentials_are_never_reposted_to_a_redirected_host(monkeypatch):
    calls = []

    async def reply(request):
        calls.append(request.url.host)
        return (
            httpx.Response(307, headers={"location": "https://untrusted.invalid/login"})
            if request.method == "POST"
            else httpx.Response(200)
        )

    cls = httpx.AsyncClient
    monkeypatch.setattr(
        portal.httpx, "AsyncClient", lambda **kw: cls(**kw, transport=httpx.MockTransport(reply))
    )
    cfg = SimpleNamespace(
        novelis=lambda: {"tarifarioUser": "fixture", "tarifarioPass": "fixture-private"}
    )
    with pytest.raises(portal.PortalError):
        asyncio.run(portal.collect(cfg))
    assert calls == ["novelis.wtmh.com.br", "novelis.wtmh.com.br"]


def test_temporary_timeout_retries_only_the_read_query_and_never_login():
    attempts = []

    async def reply(request):
        attempts.append(request.url.path)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("fixture private response", request=request)
        return httpx.Response(200, json={"data": []})

    async def run():
        async with httpx.AsyncClient(
            base_url="https://novelis.wtmh.com.br", transport=httpx.MockTransport(reply)
        ) as client:
            response = await portal.read_request(client, "POST", "/tarifa/get_tarifas/", data={})
            assert response.json() == {"data": []}

    asyncio.run(run())
    assert attempts == ["/tarifa/get_tarifas/", "/tarifa/get_tarifas/"]
