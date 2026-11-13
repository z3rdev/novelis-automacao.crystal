import asyncio
import base64
import os
import time
from pathlib import Path

import psutil
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.config.settings import Settings
from app.services.rodopar_policy import DISABLED_MESSAGE, rodopar_url_blocked
from app.services.sefaz_browser_profile import create_profile, remove_profile


class BrowserDriver:
    def __init__(self, settings: Settings, headless_override: bool | None = None) -> None:
        self.settings = settings
        self._headless_override = headless_override
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._start_lock = asyncio.Lock()
        self._snapshot_lock = asyncio.Lock()
        self._snapshot_cache: dict[str, str] | None = None
        self._snapshot_cache_at = 0.0
        self._browser_pid: int | None = None
        self.preview_override: BrowserDriver | None = None
        self.certificate: dict | None = None
        self._certificate_profile: Path | None = None

    def preview_driver(self) -> "BrowserDriver":
        child = self.preview_override
        return child if child and child.state().get("open") else self

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Navegador ainda não foi iniciado.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Contexto do navegador ainda não foi iniciado.")
        return self._context

    async def start(self) -> None:
        async with self._start_lock:
            if self._page and not self._page.is_closed():
                return
            if self._browser and self._browser.is_connected() and self._context:
                for page in reversed(self._context.pages):
                    if not page.is_closed():
                        await self.focus_page(page)
                        return
                self._page = await self._context.new_page()
                await self.focus_page(self._page)
                return

            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(self._browser_install_path())
            self._playwright = await async_playwright().start()
            context_options = {
                "accept_downloads": True,
                "ignore_https_errors": True,
                "viewport": {
                    "width": self.settings.browser_width,
                    "height": self.settings.browser_height,
                },
                "device_scale_factor": 1,
            }
            state_path = self._resolve_path(self.settings.session_state_file)
            if not self.certificate and self.settings.session_reuse and state_path.exists():
                context_options["storage_state"] = str(state_path)

            launch_options = {"headless": self._is_headless(),
                              "downloads_path": str(self.settings.browser_downloads_dir),
                              "timeout": self.settings.browser_navigation_timeout_ms, "args": self._launch_args()}
            if self.certificate:
                if self._is_headless():
                    launch_options["channel"] = "chromium"
                self._certificate_profile = create_profile(self.settings.storage_dir, self.certificate)
                self._context = await self._playwright.chromium.launch_persistent_context(
                    str(self._certificate_profile), **launch_options, **context_options,
                )
                self._browser = self._context.browser
            else:
                self._browser = await self._playwright.chromium.launch(**launch_options)
                self._context = await self._browser.new_context(**context_options)
            self._browser_pid = self._find_browser_pid()
            self._context.set_default_timeout(self.settings.browser_default_timeout_ms)
            self._context.set_default_navigation_timeout(self.settings.browser_navigation_timeout_ms)
            self._context.on("page", self._schedule_popup_focus)
            self._page = await self._context.new_page()
            await self.focus_page(self._page)

    async def new_page(self) -> Page:
        await self.start()
        old_pages = list(self.context.pages)
        self._page = await self.context.new_page()
        await self.focus_page(self._page)
        await self._close_blank_pages(old_pages, self._page)
        return self._page

    async def find_page_by_url(self, needle: str) -> Page | None:
        await self.start()
        for page in reversed(self.context.pages):
            if not page.is_closed() and needle in page.url:
                return await self.focus_page(page)
        return None

    def activate_page(self, page: Page) -> Page:
        self._page = page
        return page

    def state(self) -> dict[str, object]:
        pages: list[str] = []
        if self._context:
            for page in self._context.pages:
                try:
                    if not page.is_closed():
                        pages.append(page.url)
                except Exception:
                    continue
        connected = bool(self._browser and self._browser.is_connected())
        is_open = connected and bool(pages)
        return {
            "open": is_open,
            "connected": connected,
            "pageCount": len(pages),
            "urls": pages,
            # Only worth exposing once there's an actual page — a connected
            # browser with zero pages has no real OS window left to embed
            # (the process can stay alive as a "zombie" after its last page
            # closes), and reporting its pid anyway just sends the embed
            # feature chasing a window that no longer exists.
            "pid": self._browser_pid if is_open else None,
        }

    async def focus_page(self, page: Page) -> Page:
        self.activate_page(page)
        try:
            await page.set_viewport_size(
                {
                    "width": self.settings.browser_width,
                    "height": self.settings.browser_height,
                }
            )
        except Exception:
            pass
        try:
            session = await self.context.new_cdp_session(page)
            try:
                window = await session.send("Browser.getWindowForTarget")
                await session.send(
                    "Browser.setWindowBounds",
                    {
                        "windowId": window["windowId"],
                        "bounds": {
                            "windowState": "normal",
                            "left": 20,
                            "top": 20,
                            "width": self.settings.browser_window_width,
                            "height": self.settings.browser_window_height,
                        },
                    },
                )
            finally:
                await session.detach()
        except Exception:
            pass
        try:
            await page.bring_to_front()
        except Exception:
            pass
        return page

    async def save_storage_state(self, path: str) -> None:
        await self.start()
        await self.context.storage_state(path=path)

    async def open_url(self, url: str) -> dict[str, str]:
        if rodopar_url_blocked(self.settings, url):
            raise RuntimeError(DISABLED_MESSAGE)
        await self.start()
        await self.focus_page(self.page)
        await self.page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self.settings.browser_navigation_timeout_ms,
        )
        await self.focus_page(self.page)
        self._invalidate_snapshot()
        return await self.snapshot(max_age_ms=0)

    async def click(self, x: int, y: int) -> dict[str, str]:
        await self.start()
        await self.page.mouse.click(x, y)
        self._invalidate_snapshot()
        return await self.snapshot(max_age_ms=0)

    async def type_text(self, text: str) -> dict[str, str]:
        await self.start()
        await self.page.keyboard.type(text)
        self._invalidate_snapshot()
        return await self.snapshot(max_age_ms=0)

    async def snapshot(self, max_age_ms: int = 180) -> dict[str, str]:
        await self.start()
        cached = self._cached_snapshot(max_age_ms)
        if cached is not None:
            return cached

        async with self._snapshot_lock:
            cached = self._cached_snapshot(max_age_ms)
            if cached is not None:
                return cached

            page = self._active_page()
            image = await page.screenshot(type="jpeg", quality=68, full_page=False)
            encoded = base64.b64encode(image).decode("ascii")
            self._snapshot_cache = {"url": page.url, "image": f"data:image/jpeg;base64,{encoded}"}
            self._snapshot_cache_at = time.monotonic()
            return dict(self._snapshot_cache)

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._browser_pid = None
        self._invalidate_snapshot()
        if self._certificate_profile:
            remove_profile(self.settings.storage_dir, self._certificate_profile)
            self._certificate_profile = None
        self.certificate = None

    def _cached_snapshot(self, max_age_ms: int) -> dict[str, str] | None:
        if max_age_ms <= 0 or self._snapshot_cache is None:
            return None
        age_ms = (time.monotonic() - self._snapshot_cache_at) * 1000
        if age_ms <= max_age_ms:
            return dict(self._snapshot_cache)
        return None

    def _invalidate_snapshot(self) -> None:
        self._snapshot_cache = None
        self._snapshot_cache_at = 0.0

    def _active_page(self) -> Page:
        if self._page and not self._page.is_closed():
            return self._page
        if self._context:
            for page in reversed(self._context.pages):
                if not page.is_closed():
                    self._page = page
                    return page
        raise RuntimeError("Navegador ainda não foi iniciado.")

    def _schedule_popup_focus(self, page: Page) -> None:
        asyncio.create_task(self._focus_popup_soon(page))

    async def _focus_popup_soon(self, page: Page) -> None:
        await asyncio.sleep(0.5)
        if page.is_closed():
            return
        if page.url == "about:blank":
            return
        if not page.is_closed():
            await self.focus_page(page)

    async def _close_blank_pages(self, pages: list[Page], except_page: Page) -> None:
        for page in pages:
            if page is except_page or page.is_closed():
                continue
            if page.url != "about:blank":
                continue
            try:
                await page.close()
            except Exception:
                pass

    def _launch_args(self) -> list[str]:
        args = [
            f"--window-size={self.settings.browser_window_width},{self.settings.browser_window_height}",
            "--window-position=0,0",
            "--force-device-scale-factor=1",
            "--disable-blink-features=AutomationControlled",
        ]
        if self._is_headless():
            args.extend(
                [
                    "--use-gl=swiftshader",
                    "--enable-webgl",
                    "--disable-gpu-sandbox",
                    "--no-sandbox",
                ]
            )
        return args

    def _find_browser_pid(self) -> int | None:
        # Playwright spawns Chromium as a descendant of this process (often via an
        # intermediate driver process), so we walk the full descendant tree rather
        # than just direct children. Chromium's helper processes (renderer, gpu,
        # utility, crashpad) all carry a "--type=..." flag; only the main browser
        # process (the one that owns the visible top-level window) omits it.
        try:
            candidates = psutil.Process(os.getpid()).children(recursive=True)
        except psutil.Error:
            return None
        for candidate in candidates:
            try:
                if candidate.name().lower() not in {"chrome.exe", "chromium.exe"}:
                    continue
                cmdline = " ".join(candidate.cmdline())
                if "--type=" in cmdline:
                    continue
                if self._certificate_profile and str(self._certificate_profile) not in cmdline:
                    continue
                return candidate.pid
            except psutil.Error:
                continue
        return None

    def _is_headless(self) -> bool:
        if self._headless_override is not None:
            return self._headless_override
        return self.settings.browser_headless

    def _resolve_path(self, path_like) -> Path:
        path = Path(path_like)
        if path.is_absolute():
            return path
        return self.settings.backend_root.parent / path

    def _browser_install_path(self) -> Path:
        configured_path = self._resolve_path(self.settings.browser_playwright_path)
        if self._has_browser_install(configured_path):
            return configured_path

        default_path = self._default_playwright_path()
        if default_path and self._has_browser_install(default_path):
            return default_path

        return configured_path

    def _default_playwright_path(self) -> Path | None:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return None
        return Path(local_app_data) / "ms-playwright"

    @staticmethod
    def _has_browser_install(path: Path) -> bool:
        if not path.exists():
            return False
        browser_dirs = ("chromium*", "firefox*", "webkit*")
        return any(next(path.glob(pattern), None) is not None for pattern in browser_dirs)
