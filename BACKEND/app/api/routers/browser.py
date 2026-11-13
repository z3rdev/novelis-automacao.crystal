import re
import asyncio
import logging
from contextlib import suppress
from collections.abc import Awaitable, Callable
from typing import TypeVar
from urllib.parse import urljoin, urlparse

import httpx
import websockets
from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from starlette.requests import ClientDisconnect
from websockets.exceptions import ConnectionClosed

from app.api.deps import get_preview_browser, get_settings_from_app
from app.api.routers.browser_preview import NOOP_SERVICE_WORKER, build_preview_patch
from app.config.settings import Settings
from app.domain.models import BrowserClickRequest, BrowserOpenRequest, BrowserTypeRequest
from app.services.browser_driver import BrowserDriver
from app.services.rodopar_policy import DISABLED_MESSAGE, rodopar_url_blocked


router = APIRouter(prefix="/browser", tags=["browser"])
T = TypeVar("T")
logger = logging.getLogger(__name__)
PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
BLOCKED_FRAME_HEADERS = {
    "content-encoding",
    "content-length",
    "content-security-policy",
    "connection",
    "cross-origin-embedder-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "permissions-policy",
    "strict-transport-security",
    "transfer-encoding",
    "x-frame-options",
}


async def _browser_action(action: Callable[[], Awaitable[T]]) -> T:
    try:
        return await action()
    except HTTPException:
        raise
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Playwright não conseguiu iniciar no loop atual do Windows. "
                "Reinicie o backend pelo scripts\\run-dev.ps1 atualizado."
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha no preview do navegador: {exc}",
        ) from exc


@router.post("/open")
async def open_browser(
    payload: BrowserOpenRequest,
    settings: Settings = Depends(get_settings_from_app),
    browser: BrowserDriver = Depends(get_preview_browser),
) -> dict[str, str]:
    if rodopar_url_blocked(settings, payload.url or settings.pre_html5_url):
        raise HTTPException(status_code=409, detail=DISABLED_MESSAGE)
    return await _browser_action(lambda: browser.open_url(payload.url or settings.pre_html5_url))


@router.get("/screenshot")
async def screenshot(browser: BrowserDriver = Depends(get_preview_browser)) -> dict[str, str]:
    return await _browser_action(browser.snapshot)


@router.post("/click")
async def click(
    payload: BrowserClickRequest,
    browser: BrowserDriver = Depends(get_preview_browser),
) -> dict[str, str]:
    return await _browser_action(lambda: browser.click(payload.x, payload.y))


@router.post("/type")
async def type_text(
    payload: BrowserTypeRequest,
    browser: BrowserDriver = Depends(get_preview_browser),
) -> dict[str, str]:
    return await _browser_action(lambda: browser.type_text(payload.text))


@router.post("/close")
async def close_browser(browser: BrowserDriver = Depends(get_preview_browser)) -> dict[str, str]:
    await _browser_action(browser.close)
    return {"status": "closed"}


@router.get("/state")
async def browser_state(browser: BrowserDriver = Depends(get_preview_browser)) -> dict[str, object]:
    return browser.state()


@router.api_route("/site", methods=PROXY_METHODS)
async def proxy_site_root(
    request: Request,
    settings: Settings = Depends(get_settings_from_app),
) -> Response:
    if request.method in {"GET", "HEAD"}:
        return RedirectResponse(str(request.url).replace("/site", "/site/", 1))
    return await _proxy_site(request, settings, "")


@router.api_route("/site/{path:path}", methods=PROXY_METHODS)
async def proxy_site_path(
    path: str,
    request: Request,
    settings: Settings = Depends(get_settings_from_app),
) -> Response:
    return await _proxy_site(request, settings, path)


@router.api_route("/sefaz", methods=PROXY_METHODS)
async def proxy_sefaz_root(
    request: Request,
    settings: Settings = Depends(get_settings_from_app),
) -> Response:
    if request.method in {"GET", "HEAD"}:
        return RedirectResponse(str(request.url).replace("/sefaz", "/sefaz/", 1))
    return await _proxy_site_base(
        request,
        settings,
        "",
        "https://www.cte.fazenda.gov.br/",
        "/api/browser/sefaz/",
    )


@router.api_route("/sefaz/{path:path}", methods=PROXY_METHODS)
async def proxy_sefaz_path(
    path: str,
    request: Request,
    settings: Settings = Depends(get_settings_from_app),
) -> Response:
    return await _proxy_site_base(
        request,
        settings,
        path,
        "https://www.cte.fazenda.gov.br/",
        "/api/browser/sefaz/",
    )


@router.websocket("/site/socket.io/websocket/{path:path}")
async def proxy_site_websocket(
    path: str,
    websocket: WebSocket,
) -> None:
    settings: Settings = websocket.app.state.settings
    if rodopar_url_blocked(settings, settings.pre_url):
        await websocket.close(code=1008)
        return
    target_url = _target_ws_url(settings.pre_url, f"socket.io/websocket/{path}", websocket.url.query)
    headers = _websocket_upstream_headers(websocket, settings.pre_url)
    subprotocols = _websocket_subprotocols(websocket)
    user_agent = headers.pop("user-agent", None)

    try:
        async with websockets.connect(
            target_url,
            origin=_origin(settings.pre_url),
            additional_headers=headers,
            subprotocols=subprotocols,
            user_agent_header=user_agent,
            proxy=None,
            open_timeout=20,
            ping_interval=None,
            max_size=None,
        ) as upstream:
            await websocket.accept(subprotocol=upstream.subprotocol)
            await _pipe_websocket(websocket, upstream)
    except Exception as exc:
        logger.warning("Preview WebSocket proxy failed for %s: %s", target_url, exc)
        with suppress(Exception):
            await websocket.close(code=1011)


async def _proxy_site(request: Request, settings: Settings, path: str) -> Response:
    return await _proxy_site_base(request, settings, path, settings.pre_url, "/api/browser/site/")


async def _proxy_site_base(
    request: Request,
    settings: Settings,
    path: str,
    base_url: str,
    proxy_prefix: str,
) -> Response:
    if _is_service_worker_path(path):
        return _service_worker_response()

    target_url = _target_url(base_url, path, request.url.query)
    if rodopar_url_blocked(settings, target_url):
        return Response(status_code=410, content=DISABLED_MESSAGE)
    headers = _upstream_headers(request, base_url)
    try:
        content = b"" if request.method in {"GET", "HEAD"} else await request.body()
    except ClientDisconnect:
        return Response(status_code=499)

    client = _upstream_client(request)
    try:
        upstream = await client.request(
            request.method,
            target_url,
            content=content,
            headers=headers,
        )
    except asyncio.CancelledError:
        return Response(status_code=499)
    except httpx.HTTPError as exc:
        logger.warning("Preview proxy upstream failed for %s: %s", target_url, exc)
        return Response(status_code=502, content="Preview proxy upstream failed")

    body = _rewrite_body(upstream, settings, path, base_url, proxy_prefix)
    response = Response(
        content=body,
        status_code=upstream.status_code,
        headers=_downstream_headers(upstream, base_url, proxy_prefix),
        media_type=upstream.headers.get("content-type"),
    )
    for cookie in upstream.headers.get_list("set-cookie"):
        response.headers.append("set-cookie", _rewrite_cookie(cookie, proxy_prefix))
    return response


def _upstream_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "preview_proxy_client", None)
    if client is not None and not client.is_closed:
        return client

    timeout = httpx.Timeout(connect=10, read=75, write=30, pool=10)
    limits = httpx.Limits(max_connections=80, max_keepalive_connections=30, keepalive_expiry=120)
    client = httpx.AsyncClient(follow_redirects=False, timeout=timeout, limits=limits)
    request.app.state.preview_proxy_client = client
    return client


async def _pipe_websocket(client: WebSocket, upstream) -> None:
    tasks = {
        asyncio.create_task(_client_to_upstream(client, upstream)),
        asyncio.create_task(_upstream_to_client(upstream, client)),
    }
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in done:
        with suppress(WebSocketDisconnect, ConnectionClosed):
            task.result()
    with suppress(Exception):
        await upstream.close()
    with suppress(Exception):
        await client.close()


async def _client_to_upstream(client: WebSocket, upstream) -> None:
    while True:
        message = await client.receive()
        if message["type"] == "websocket.disconnect":
            return
        if message.get("text") is not None:
            await upstream.send(message["text"])
        elif message.get("bytes") is not None:
            await upstream.send(message["bytes"])


async def _upstream_to_client(upstream, client: WebSocket) -> None:
    async for message in upstream:
        if isinstance(message, bytes):
            await client.send_bytes(message)
        else:
            await client.send_text(message)


def _is_service_worker_path(path: str) -> bool:
    return path.lower().rstrip("/").endswith("sw.js")


def _service_worker_response() -> Response:
    return Response(
        content=NOOP_SERVICE_WORKER,
        media_type="application/javascript",
        headers={
            "cache-control": "no-store, no-cache, must-revalidate",
            "clear-site-data": '"cache"',
        },
    )


def _target_url(base_url: str, path: str, query: str) -> str:
    target = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    if query:
        return f"{target}?{query}"
    return target


def _target_ws_url(base_url: str, path: str, query: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    target = urljoin(f"{scheme}://{parsed.netloc}/", path.lstrip("/"))
    if query:
        return f"{target}?{query}"
    return target


def _upstream_headers(request: Request, base_url: str) -> dict[str, str]:
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    allowed = {"accept", "accept-language", "content-type", "cookie", "user-agent"}
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() in allowed
    }
    headers["origin"] = origin
    headers["referer"] = base_url
    return headers


def _websocket_upstream_headers(websocket: WebSocket, base_url: str) -> dict[str, str]:
    allowed = {"accept-language", "cookie", "user-agent"}
    headers = {
        key.lower(): value
        for key, value in websocket.headers.items()
        if key.lower() in allowed
    }
    headers["referer"] = base_url
    return headers


def _websocket_subprotocols(websocket: WebSocket) -> list[str] | None:
    header = websocket.headers.get("sec-websocket-protocol")
    if not header:
        return None
    protocols = [item.strip() for item in header.split(",") if item.strip()]
    return protocols or None


def _downstream_headers(
    upstream: httpx.Response,
    base_url: str,
    proxy_prefix: str,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in upstream.headers.items():
        lowered = key.lower()
        if lowered in BLOCKED_FRAME_HEADERS or lowered == "set-cookie":
            continue
        if lowered == "location":
            value = _rewrite_location(value, base_url, proxy_prefix)
        headers[key] = value
    headers["cache-control"] = "no-store"
    return headers


def _rewrite_location(location: str, base_url: str, proxy_prefix: str) -> str:
    origin = _origin(base_url)
    if location.startswith(origin):
        return proxy_prefix + location.removeprefix(origin).lstrip("/")
    if location.startswith("/") and not location.startswith("//"):
        return proxy_prefix + location.lstrip("/")
    return location


def _rewrite_body(
    upstream: httpx.Response,
    settings: Settings,
    path: str,
    base_url: str,
    proxy_prefix: str,
) -> bytes:
    content_type = upstream.headers.get("content-type", "").lower()
    rewrite_types = ("text/html", "text/css", "javascript", "application/json")
    if not any(item in content_type for item in rewrite_types):
        return upstream.content

    text = upstream.text
    origin = _origin(base_url)
    text = text.replace(f"{origin}/", proxy_prefix)
    text = text.replace(base_url.rstrip("/") + "/", proxy_prefix)
    text = _rewrite_root_relative_urls(text, proxy_prefix)
    if "webcloud16.datapardc.com" in origin:
        text = _rewrite_datapar_preview_settings(text)
    if _should_inject_preview_patch(text, content_type, path):
        text = _inject_preview_navigation_patch(text, settings, proxy_prefix, origin)
    return text.encode(upstream.encoding or "utf-8")


def _rewrite_root_relative_urls(text: str, proxy_prefix: str) -> str:
    text = re.sub(
        r'(?i)\b(href|src|action)=([\'"])/(?!/)',
        rf"\1=\2{proxy_prefix}",
        text,
    )
    text = re.sub(r"(?i)\burl\(/(?!/)", f"url({proxy_prefix}", text)
    return text


def _should_inject_preview_patch(text: str, content_type: str, path: str) -> bool:
    if "text/html" not in content_type:
        return False
    if _looks_like_api_response(text):
        return False
    lowered_path = path.lower()
    if lowered_path.endswith(".js") or "/cgi-bin/" in lowered_path or "socket.io/" in lowered_path:
        return False
    return _looks_like_html_document(text)


def _looks_like_api_response(text: str) -> bool:
    stripped = text.lstrip("\ufeff\r\n\t ")
    return stripped.startswith("{") or stripped.startswith("[")


def _looks_like_html_document(text: str) -> bool:
    lowered = text.lstrip("\ufeff\r\n\t ").lower()
    return lowered.startswith("<!doctype") or lowered.startswith("<html") or "<head" in lowered or "<body" in lowered


def _rewrite_datapar_preview_settings(text: str) -> str:
    if "W.gooutofiframe" not in text and "W.openinsideopener" not in text:
        return text

    replacements = {
        r"\bW\.gooutofiframe\s*=\s*true\s*;": "W.gooutofiframe = false;",
        r"\bW\.openinsideopener\s*=\s*true\s*;": "W.openinsideopener = false;",
        r"\bW\.callparentclose\s*=\s*true\s*;": "W.callparentclose = false;",
        r"\bW\.nowarnings\s*=\s*false\s*;": "W.nowarnings = true;",
        r"\bW\.xhrreverse\s*=\s*(true|false)\s*;": "W.xhrreverse = true;",
        r"\bW\.disablewebsocket\s*=\s*(true|false)\s*;": "W.disablewebsocket = true;",
        r"\bW\.reverseproxy\s*=\s*(true|false)\s*;": "W.reverseproxy = true;",
        r"\bW\.informOnBadConnection\s*=\s*true\s*;": "W.informOnBadConnection = false;",
        r"\bW\.connectionmessage\s*=\s*true\s*;": "W.connectionmessage = false;",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    override = (
        "try { W.gooutofiframe = false; W.openinsideopener = false; "
        "W.callparentclose = false; W.nowarnings = true; W.xhrreverse = true; "
        "W.disablewebsocket = true; W.reverseproxy = true; W.underIframe = true; "
        "W.informOnBadConnection = false; W.connectionmessage = false; } catch (_e) {}\n"
    )
    return override + text + "\n" + override


def _inject_preview_navigation_patch(
    text: str,
    settings: Settings,
    proxy_prefix: str,
    remote_origin: str,
) -> str:
    if "__automationNovelisPreviewPatch" in text:
        return text

    patch = build_preview_patch(settings, text, proxy_prefix, remote_origin)
    lower_text = text.lower()
    head_start = lower_text.find("<head")
    if head_start >= 0:
        head_end = text.find(">", head_start)
        if head_end >= 0:
            return text[: head_end + 1] + patch + text[head_end + 1 :]

    body_start = lower_text.find("<body")
    if body_start >= 0:
        body_end = text.find(">", body_start)
        if body_end >= 0:
            return text[: body_end + 1] + patch + text[body_end + 1 :]

    return patch + text


def _rewrite_cookie(cookie: str, proxy_prefix: str) -> str:
    parts = []
    for item in cookie.split(";"):
        value = item.strip()
        lowered = value.lower()
        if lowered == "secure" or lowered.startswith("domain=") or lowered.startswith("path="):
            continue
        if lowered == "samesite=none":
            parts.append("SameSite=Lax")
        else:
            parts.append(value)
    parts.append(f"Path={proxy_prefix.rstrip('/')}")
    return "; ".join(parts)


def _origin(base_url: str) -> str:
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}"
