import asyncio
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.automation.flows.sefaz_xml.overlay.fazenda_overlay import (
    click_and_wait_maybe_navigates,
    is_locator_visible,
    update_fazenda_overlay,
    wait_for_captcha_marked,
    wait_for_visible_or_manual,
    wait_if_paused,
)
from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.automation.cancellation import check_cancelled, run_blocking
from app.domain.models import RunStartRequest
from app.infrastructure.json_store import read_json
from app.services.browser_driver import BrowserDriver
from app.services.cte_xml_files import validate_download
from app.services.sefaz_certificate import configure_certificate


FAZENDA_URL = (
    "https://www.cte.fazenda.gov.br/portal/consultaRecaptcha.aspx"
    "?tipoConsulta=completa&tipoConteudo=mCK/KoCqru0="
)

SELECTORS = {
    "chave": "#ctl00_ContentPlaceHolder1_txtChaveAcessoResumo",
    "continuar": "#ctl00_ContentPlaceHolder1_btnConsultarHCaptcha",
    "consulta_completa": "#ctl00_ContentPlaceHolder1_btnConsultaCompleta",
    "download": "#ctl00_ContentPlaceHolder1_btnDownload",
}


class XmlSefazFlow:
    def __init__(self, cwd: Path, emit: Emit) -> None:
        self.cwd = cwd
        self.emit = emit

    async def run(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> dict[str, Any] | None:
        target = self._resolve_target(config, request)
        if not target:
            await emit_warn(
                self.emit,
                run_id,
                "xml_sefaz.no_target",
                "Informe um CTE teste completo ou chave CTe para baixar XML.",
            )
            return None

        await emit_step(
            self.emit,
            run_id,
            "xml_sefaz.target",
            f"XML Sefaz preparado para {target['cte']}.",
            target,
        )
        if request.dry_run:
            await emit_step(self.emit, run_id, "xml_sefaz.dry_run", "XML Sefaz simulado.")
            return target
        if browser is None:
            raise RuntimeError("BrowserDriver obrigatório para XML Sefaz real.")
        if not target.get("cteId"):
            raise RuntimeError("XML Sefaz precisa da chave CTe de 44 digitos ou fonte JSON com cteId.")

        cert = await run_blocking(configure_certificate, config)
        if browser.certificate != cert and browser.state().get("open"):
            await browser.close()
        browser.certificate = cert
        if cert:
            await emit_step(self.emit, run_id, "xml_sefaz.certificate",
                            f"Certificado Windows selecionado automaticamente: {cert['subjectCN']}.",
                            {"cte": target["cte"], "expiresAt": cert["notAfter"]})
        page = await self._fazenda_page(browser)
        return await self._download_xml(page, config, target, run_id)

    async def _download_xml(
        self,
        page: Page,
        config: dict[str, Any],
        target: dict[str, Any],
        run_id: str,
    ) -> dict[str, Any]:
        await emit_step(self.emit, run_id, "xml_sefaz.open", "Abrindo consulta CTe Sefaz.")
        state = {"cte": target["cte"], "cteId": target["cteId"]}
        self._install_dialog_handler(page)
        await page.goto(str(config.get("url") or FAZENDA_URL), wait_until="domcontentloaded")
        await page.bring_to_front()
        await update_fazenda_overlay(
            page,
            {
                **state,
                "phase": "Preenchendo chave",
                "message": "Preenchendo a chave de acesso no portal da Fazenda.",
                "showPrimary": False,
            },
        )
        await wait_if_paused(page, state)

        input_field = page.locator(SELECTORS["chave"]).first
        await input_field.wait_for(state="visible", timeout=45_000)
        access_key = self._access_key(target["cteId"])
        await input_field.fill("")
        await input_field.type(access_key, delay=int(config.get("typeDelayMs") or 5))
        await input_field.evaluate(
            """(field) => {
              field.dispatchEvent(new Event("input", { bubbles: true }));
              field.dispatchEvent(new Event("change", { bubbles: true }));
            }"""
        )
        await emit_step(
            self.emit,
            run_id,
            "xml_sefaz.captcha",
            "Chave preenchida. Tentando clicar no hCaptcha; conclua eventuais desafios no navegador.",
        )
        await wait_for_captcha_marked(
            page,
            {**state, "phase": "hCaptcha"},
            timeout_ms=int(config.get("captchaTimeoutMs") or 180_000),
        )
        await emit_step(self.emit, run_id, "xml_sefaz.consulting", "Confirmacao recebida; consultando e baixando o XML.", {"cte": target["cte"]})
        await self._click_continuar(page, state, config)
        await self._click_consulta_completa(page, state, config)
        download_button = await self._download_button(page, state, config)

        output_dir = self._resolve(config.get("downloadDir") or "captures/cte-fazenda-downloads")
        output_dir.mkdir(parents=True, exist_ok=True)
        await update_fazenda_overlay(
            page,
            {
                **state,
                "phase": "Download",
                "message": "Clicando em Download do documento e aguardando o XML.",
                "showPrimary": False,
            },
        )
        await wait_if_paused(page, state)
        download = await self._perform_download(page, download_button, state, config)
        file_name = f"CTE_{self._safe_name(target['cte'])}.xml"
        file_path = output_dir / file_name
        temporary = output_dir / f".{file_name}.{uuid4().hex}.partial"
        try:
            await download.save_as(str(temporary))
            await run_blocking(self._publish_xml, temporary, file_path, target)
        finally:
            temporary.unlink(missing_ok=True)
        await self._cleanup_download_artifact(download, file_path)
        result = {**target, "xmlFile": str(file_path)}
        await update_fazenda_overlay(
            page,
            {
                **state,
                "phase": "Concluido",
                "message": f"XML salvo: {file_path.name}",
                "showPrimary": False,
            },
        )
        await emit_step(self.emit, run_id, "xml_sefaz.saved", f"XML salvo em {file_path}.", result)
        return result

    @staticmethod
    def _publish_xml(temporary: Path, destination: Path, target: dict) -> None:
        validate_download(temporary, target)
        check_cancelled()
        temporary.replace(destination)

    async def _fazenda_page(self, browser: BrowserDriver) -> Page:
        page = await browser.find_page_by_url("cte.fazenda.gov.br")
        if page is None:
            page = await browser.new_page()
        browser.activate_page(page)
        await page.bring_to_front()
        return page

    def _install_dialog_handler(self, page: Page) -> None:
        if getattr(page, "_automacao_novelis_dialog_handler", False):
            return
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
        setattr(page, "_automacao_novelis_dialog_handler", True)

    async def _perform_download(
        self,
        page: Page,
        download_button,
        state: dict[str, Any],
        config: dict[str, Any],
    ):
        try:
            async with page.expect_download(timeout=int(config.get("downloadTimeoutMs") or 120_000)) as download_info:
                await download_button.click(timeout=45_000)
            return await download_info.value
        except Exception:
            await update_fazenda_overlay(
                page,
                {
                    **state,
                    "phase": "Download manual",
                    "message": (
                        "O download automático não iniciou. Se apareceu certificado ou confirmação, "
                        "resolva na janela, clique em Download do documento e eu continuo aguardando."
                    ),
                    "primaryLabel": "Aguardando download",
                    "showPrimary": True,
                },
            )
        return await page.wait_for_event(
            "download",
            timeout=int(config.get("manualDownloadTimeoutMs") or 600_000),
        )

    async def _cleanup_download_artifact(self, download: Any, saved_file: Path) -> None:
        try:
            artifact = Path(await download.path())
        except Exception:
            return
        try:
            if artifact.exists() and artifact.resolve() != saved_file.resolve():
                artifact.unlink()
        except OSError:
            return

    async def _click_continuar(
        self,
        page: Page,
        state: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        await update_fazenda_overlay(
            page,
            {
                **state,
                "phase": "Continuar",
                "message": "Clicando no botão Continuar da Fazenda.",
                "showPrimary": False,
            },
        )
        await wait_if_paused(page, state)
        continuar = page.locator(SELECTORS["continuar"]).first
        if await is_locator_visible(continuar):
            await click_and_wait_maybe_navigates(
                page,
                continuar,
                int(config.get("navigationTimeoutMs") or 90_000),
            )

    async def _click_consulta_completa(
        self,
        page: Page,
        state: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        consulta_completa = await wait_for_visible_or_manual(
            page,
            SELECTORS["consulta_completa"],
            "Consulta Completa",
            int(config.get("consultaCompletaTimeoutMs") or 60_000),
            (
                "Não achei o botão Consulta Completa. Se pediu certificado ou a página "
                "ainda esta carregando, resolva na tela e clique Continuar no overlay."
            ),
            state,
        )
        await update_fazenda_overlay(
            page,
            {
                **state,
                "phase": "Consulta completa",
                "message": "Clicando em Consulta Completa.",
                "showPrimary": False,
            },
        )
        await wait_if_paused(page, state)
        await click_and_wait_maybe_navigates(
            page,
            consulta_completa,
            int(config.get("navigationTimeoutMs") or 90_000),
        )

    async def _download_button(
        self,
        page: Page,
        state: dict[str, Any],
        config: dict[str, Any],
    ):
        return await wait_for_visible_or_manual(
            page,
            SELECTORS["download"],
            "Download do documento",
            int(config.get("downloadButtonTimeoutMs") or 60_000),
            (
                "Se apareceu seletor de certificado, escolha e confirme. Quando o botão "
                "Download do documento estiver visivel, clique Continuar no overlay."
            ),
            state,
        )

    async def _click_if_visible(self, page: Page, selector: str, timeout: int) -> bool:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=timeout)
            await locator.click()
            return True
        except Exception:
            return False

    async def _wait_hcaptcha(self, page: Page, config: dict[str, Any]) -> None:
        timeout = int(config.get("captchaTimeoutMs") or 180_000)
        captcha = page.locator("textarea[name='h-captcha-response']").first
        try:
            await captcha.wait_for(state="attached", timeout=5_000)
        except Exception:
            return
        try:
            await page.wait_for_function(
                """() => Array.from(document.querySelectorAll("textarea[name='h-captcha-response']"))
                  .some((field) => String(field.value || "").trim().length > 0)""",
                timeout=timeout,
            )
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Captcha da Sefaz não foi resolvido dentro do tempo.") from exc

    def _access_key(self, value: Any) -> str:
        return re.sub(r"\D+", "", str(value or "").replace("CTe", ""))

    def _resolve_target(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
    ) -> dict[str, Any] | None:
        raw = str(config.get("ctes") or request.sample_cte or "").strip()
        target = self._parse_target(raw, config)
        if target and target.get("cteId"):
            return target
        source = self._lookup_source_json(config, target)
        return source or target

    def _lookup_source_json(
        self,
        config: dict[str, Any],
        target: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        source_value = str(config.get("sourceJson") or "").strip()
        if not source_value:
            return None
        source_json = self._resolve(source_value)
        if not source_json.is_file():
            return None
        payload = read_json(source_json, {})
        rows = []
        if isinstance(payload, dict):
            for key in ("rows", "needed", "items"):
                if isinstance(payload.get(key), list):
                    rows.extend(payload[key])
        elif isinstance(payload, list):
            rows = payload
        target_key = target.get("key") if target else ""
        for row in rows:
            parsed = self._parse_target(row, config)
            if parsed and (not target_key or parsed.get("key") == target_key) and parsed.get("cteId"):
                return parsed
        return None

    def _parse_target(
        self,
        value: Any,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        if isinstance(value, dict):
            raw_key = value.get("cteId") or value.get("CTE_ID") or value.get("chave") or ""
            parsed = self._parse_access_key(raw_key)
            filial = self._part(
                value.get("filial")
                or value.get("FILIAL")
                or (parsed.get("filial") if parsed else "")
            )
            serie = self._part(
                value.get("serie")
                or value.get("SERIE")
                or (parsed.get("serie") if parsed else "")
            )
            doc = self._part(
                value.get("documento")
                or value.get("DOCUMENTO")
                or value.get("nCT")
                or value.get("NCT")
                or (parsed.get("documento") if parsed else "")
            )
            if not filial or not serie or not doc:
                return parsed
            return self._target(filial, serie, doc, parsed.get("cteId", "") if parsed else "")

        raw = str(value or "").strip()
        parsed = self._parse_access_key(raw)
        if parsed:
            return parsed
        parts = [part for part in re.split(r"[-/\s,;]+", raw) if part]
        if len(parts) >= 3:
            return self._target(parts[0], parts[1], "".join(parts[2:]), "")
        if len(parts) == 1 and parts[0].isdigit() and config.get("defaultFilial"):
            return self._target(config.get("defaultFilial"), config.get("defaultSerie") or "10", parts[0], "")
        return None

    def _parse_access_key(self, value: Any) -> dict[str, Any] | None:
        digits = re.sub(r"\D+", "", str(value or "").replace("CTe", ""))
        if len(digits) != 44:
            return None
        cnpj = digits[6:20]
        return self._target(cnpj[8:12], digits[22:25], digits[25:34], digits)

    def _target(self, filial: Any, serie: Any, documento: Any, cte_id: str) -> dict[str, Any]:
        item = {
            "filial": self._part(filial),
            "serie": self._part(serie),
            "documento": self._part(documento),
            "cteId": cte_id,
        }
        item["cte"] = f"{item['filial']}-{item['serie']}-{item['documento']}"
        item["key"] = f"{item['filial']}|{item['serie']}|{item['documento']}"
        return item

    def _part(self, value: Any) -> str:
        digits = re.sub(r"\D+", "", str(value or ""))
        return digits.lstrip("0") or digits or str(value or "").strip().upper()

    def _safe_name(self, value: Any) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "cte")).strip("_")

    def _resolve(self, value: str) -> Path:
        path = Path(str(value or ""))
        return path if path.is_absolute() else self.cwd / path
