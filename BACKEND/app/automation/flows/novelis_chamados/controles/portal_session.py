"""Reuse the browser context's session; authenticate only after a protected GET requests it."""

from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeout

from app.automation.flows.flow_events import emit_step


def official(url):
    parsed = urlsplit(str(url))
    if parsed.scheme != "https" or parsed.netloc != "novelis.wtmh.com.br":
        raise RuntimeError("Configure o endereço HTTPS oficial do portal Novelis.")
    return str(url)


async def needs_login(page):
    if urlsplit(page.url).path.rstrip("/") == "/login":
        return True
    return await page.locator('input[type="password"]').first.is_visible()


async def open_authenticated(page, target, config, emit, run_id):
    """Retry navigation once after login, never repeat a save/upload request."""
    target = official(target)
    await emit_step(
        emit, run_id, "novelis.session_check", "Novelis: verificando a sessão existente."
    )
    response = await page.goto(target, wait_until="domcontentloaded")
    if response is not None and response.status in {401, 403} and not await needs_login(page):
        raise RuntimeError("O portal Novelis recusou acesso à página protegida.")
    official(page.url)
    if not await needs_login(page):
        await emit_step(
            emit, run_id, "novelis.session_reused", "Novelis: sessão reaproveitada, sem novo login."
        )
        return
    if not config.get("user") or not config.get("pass"):
        raise RuntimeError("A sessão Novelis expirou. Configure a conta de acesso no backend.")
    login = official(config.get("loginUrl") or "https://novelis.wtmh.com.br/login")
    if urlsplit(page.url).path.rstrip("/") != "/login":
        await page.goto(login, wait_until="domcontentloaded")
    await emit_step(
        emit, run_id, "novelis.login", "Novelis: sessão ausente ou expirada; autenticando."
    )
    await page.locator('input[type="email"], input[name="email"], #email').first.fill(
        str(config["user"])
    )
    await page.locator('input[type="password"]').first.fill(str(config["pass"]))
    await page.locator('button[type="submit"], input[type="submit"]').first.click()
    try:
        await page.wait_for_url(
            lambda url: urlsplit(str(url)).path.rstrip("/") != "/login", timeout=15000
        )
    except PlaywrightTimeout:
        raise RuntimeError(
            "Login Novelis não confirmado. Verifique a conta ou a autenticação no navegador."
        ) from None
    official(page.url)
    await page.goto(target, wait_until="domcontentloaded")
    if await needs_login(page):
        raise RuntimeError("O portal Novelis não manteve a sessão após o login.")
    await emit_step(
        emit,
        run_id,
        "novelis.session_ready",
        "Novelis: sessão autenticada para os próximos chamados.",
    )
