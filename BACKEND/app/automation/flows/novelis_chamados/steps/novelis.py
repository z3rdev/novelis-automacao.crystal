import re
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.automation.flows.novelis_chamados.controles.chamado_controls import (
    detect_page_cte,
    select_chamado_item,
    upload_file_by_field,
    wait_chamado_form_ready,
    wait_upload_fields_ready,
)
from app.automation.flows.novelis_chamados.controles.evidence import resolve_chamado_upload_files
from app.automation.flows.novelis_chamados.controles.form import (
    fill_chamado_title_message,
    inspect_required_fields,
    is_required_form_error,
)
from app.automation.flows.novelis_chamados.controles.save import click_salvar_chamado, wait_save_confirmation
from app.automation.flows.novelis_chamados.overlay.novelis_overlay import (
    update_novelis_overlay,
    wait_if_novelis_paused,
)
from app.automation.flows.tarifario.steps.tarifario import TarifarioFlow
from app.services.browser_driver import BrowserDriver


from .novelis_support import NovelisSupport
from app.services.chamado_message import render_message
from app.services.execution_reports.models import ticket
from app.automation.flows.novelis_chamados.controles.portal_session import open_authenticated


class NovelisFlow(NovelisSupport):
    def __init__(self, cwd: Path, emit: Emit, http_session=None) -> None:
        self.cwd = cwd
        self.emit = emit
        self.http_session = http_session

    async def run(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        request,
        run_id: str,
    ) -> list[dict[str, Any]] | None:
        tarifario_rows = None
        if config.get("enableTarifarioStep") and not config.get("directChamadoMode"):
            tarifario_rows = await TarifarioFlow(self.cwd, self.emit).run(browser, config, request, run_id)
            if not config.get("openChamadoAfterTarifario"):
                await emit_step(self.emit, run_id, "novelis.tarifario_only", "Encerrado após tarifário.")
                return tarifario_rows
            if tarifario_rows == []:
                await emit_warn(self.emit, run_id, "novelis.no_tarifario", "Sem tarifa para abrir chamado.")
                return tarifario_rows

        if request.dry_run:
            row = self._resolve_tarifario_row(config)
            await emit_step(
                self.emit,
                run_id,
                "novelis.dry_run",
                "Chamado simulado.",
                {"messagePreview": self.build_chamado_message(row, config.get("chamadoAssinatura", ""))},
            )
            return tarifario_rows

        row = self._resolve_tarifario_row(config)
        if self.http_session:
            await self.http_session.open(row, config, send=config.get("chamadoSalvar", True))
        else:
            from app.services.novelis_chamado_http.session import HttpChamadosSession
            async with HttpChamadosSession(self.cwd, config, self.emit, run_id) as session:
                await session.open(row, config, send=config.get("chamadoSalvar", True))
        return tarifario_rows

    async def run_chamado_flow(self, page: Page, config: dict[str, Any], run_id: str) -> None:
        row = self._resolve_tarifario_row(config)
        state = self._overlay_state(row)
        await page.bring_to_front()
        await update_novelis_overlay(
            page,
            {
                **state,
                "phase": "Preparando",
                "message": "Preparando abertura de chamado Novelis.",
            },
        )
        await wait_if_novelis_paused(page, state)
        existing = self._find_existing_chamado(config, row)
        if existing:
            numero = str(existing.get("chamadoNumero") or existing.get("chamadoId") or "")
            await emit_warn(
                self.emit,
                run_id,
                "novelis.chamado_exists",
                f"CTE já consta na lista Novelis: {numero}.",
                {"ticket": ticket(row, numero)},
            )
            self._mark_processed(config, row, "ja_existia", numero)
            await update_novelis_overlay(
                page,
                {
                    **state,
                    "phase": "Ja existe",
                    "message": "CTE já consta na lista Novelis. Chamado não será aberto.",
                },
            )
            return

        await emit_step(self.emit, run_id, "novelis.open_chamado", "Abrindo tela de chamado.")
        page = await self._open_chamado_screen(page, config, state, run_id)
        await self._ensure_page_cte_matches(page, row, run_id, state, "após abrir tela de chamado")
        if await self._skip_if_chamado_already_exists(page, config, row, run_id, state):
            return
        await update_novelis_overlay(
            page,
            {
                **state,
                "phase": "Selecionando item",
                "message": "Selecionando o item configurado para o chamado.",
            },
        )
        await wait_if_novelis_paused(page, state)
        await self._select_item(page, str(config.get("chamadoItem") or ""))
        await page.wait_for_timeout(800)
        await self._ensure_page_cte_matches(page, row, run_id, state, "após selecionar tipo")
        if await self._skip_if_chamado_already_exists(page, config, row, run_id, state):
            return
        await self._upload_files_if_present(page, row, config, run_id, state)
        await self._fill_title_message(page, row, config, run_id, state)
        if config.get("chamadoSalvar", True):
            await self._save_chamado(page, row, config, run_id, state)

    async def ensure_portal_authenticated(
        self,
        page: Page,
        config: dict[str, Any],
        run_id: str,
        state: dict[str, Any] | None = None,
    ) -> None:
        target = config.get("dashboardUrl") or config.get("portalUrl") or "https://novelis.wtmh.com.br/portal/dashboard"
        await open_authenticated(page, target, config, self.emit, run_id)

    async def _select_item(self, page: Page, item_text: str) -> None:
        await select_chamado_item(page, item_text)

    async def _open_chamado_screen(self, page: Page, config: dict[str, Any], state: dict[str, Any], run_id: str) -> Page:
        if config.get("chamadoPreferDirectUrl", True):
            direct_url = self._direct_chamado_url(config)
            if not direct_url:
                raise RuntimeError("Configure NOVELIS_CHAMADO_DIRETO_URL ou NOVELIS_PORTAL_URL para abrir chamado.")
            await update_novelis_overlay(
                page,
                {**state, "phase": "Abrindo chamado", "message": "Abrindo chamado pela URL direta."},
            )
            await wait_if_novelis_paused(page, state)
            await open_authenticated(page, direct_url, config, self.emit, run_id)
            if await wait_chamado_form_ready(page, 18_000):
                return page
            if not config.get("chamadoWorkflowFallback", False):
                raise RuntimeError(
                    f"URL direta do chamado não ficou pronta: {direct_url}. "
                    "Fallback workflow/entrada esta desligado para evitar chamado errado."
                )

        chamado_url = self._required_url(config, "chamadoEntradaUrl", "NOVELIS_CHAMADO_ENTRADA_URL")
        await update_novelis_overlay(
            page,
            {**state, "phase": "Abrindo chamado", "message": "Abrindo a tela de entrada do chamado."},
        )
        await wait_if_novelis_paused(page, state)
        await open_authenticated(page, chamado_url, config, self.emit, run_id)
        return page

    async def _fill_title_message(
        self,
        page: Page,
        row: dict[str, Any],
        config: dict[str, Any],
        run_id: str,
        state: dict[str, Any],
    ) -> None:
        await update_novelis_overlay(
            page,
            {
                **state,
                "phase": "Mensagem",
                "message": "Preenchendo titulo e mensagem do chamado.",
            },
        )
        await wait_if_novelis_paused(page, state)
        title = render_message(row, str(config.get("chamadoAssinatura") or ""), str(config.get("chamadoTitulo") or "CTE {cte}"))
        template = config.get("chamadoMensagemComplementar") if self._is_complementar(row) else config.get("chamadoMensagem")
        message = self.build_chamado_message(row, str(config.get("chamadoAssinatura") or ""), template)
        fill_result = await fill_chamado_title_message(page, title, message)
        required = await inspect_required_fields(page)
        if "Mensagem" in required.get("missing", []):
            raise RuntimeError("Campo obrigatório Mensagem não foi preenchido no Novelis.")
        await emit_step(self.emit, run_id, "novelis.message", "Título e mensagem preenchidos.", fill_result)
        await update_novelis_overlay(
            page,
            {
                **state,
                "phase": "Mensagem",
                "message": "Título e mensagem preenchidos.",
            },
        )

    async def _upload_files_if_present(
        self,
        page: Page,
        row: dict[str, Any],
        config: dict[str, Any],
        run_id: str,
        state: dict[str, Any],
    ) -> None:
        if not config.get("chamadoUploadFromTarifario", True):
            await emit_warn(self.emit, run_id, "novelis.upload_disabled", "Upload automático do chamado desativado.")
            return

        await update_novelis_overlay(
            page,
            {
                **state,
                "phase": "Anexos",
                "message": "Aguardando campos de upload do chamado.",
            },
        )
        await wait_if_novelis_paused(page, state)
        if not await wait_upload_fields_ready(page, 30_000):
            raise RuntimeError("Campos de upload do chamado não apareceram após selecionar o tipo.")

        files = resolve_chamado_upload_files(self.cwd, config, row)
        evidence = config.get("evidence") or {}
        if evidence.get("requiresComprovante") and not evidence.get("comprovanteOk") and not config.get("allowMissingComprovante", False):
            raise RuntimeError("Abertura sem comprovante desabilitada nas configurações de mensagens.")
        attempts = 1 + max(0, self._int(config.get("chamadoUploadRetryAttempts"), 1))
        retry_delay_ms = max(0, self._int(config.get("chamadoUploadRetryDelayMs"), 1500))
        await update_novelis_overlay(
            page,
            {
                **state,
                "phase": "Anexos",
                "message": f"Anexando PDF, XML e ZIP do CTE {files['documento']}.",
            },
        )
        await upload_file_by_field(page, "arquivo[0]", files["pdfFile"], "PDF", attempts, retry_delay_ms)
        await upload_file_by_field(page, "arquivo[1]", files["xmlFile"], "XML", attempts, retry_delay_ms)
        await upload_file_by_field(page, "arquivo[2]", files["zipFile"], "ZIP", attempts, retry_delay_ms)
        await page.wait_for_timeout(800)
        await emit_step(
            self.emit,
            run_id,
            "novelis.upload_completed",
            f"Anexos enviados: {Path(files['pdfFile']).name}, {Path(files['xmlFile']).name}, {Path(files['zipFile']).name}.",
            {"files": files},
        )

    async def _save_chamado(
        self,
        page: Page,
        row: dict[str, Any],
        config: dict[str, Any],
        run_id: str,
        state: dict[str, Any],
    ) -> None:
        await update_novelis_overlay(
            page,
            {
                **state,
                "phase": "Salvar",
                "message": "Salvando chamado Novelis.",
            },
        )
        await wait_if_novelis_paused(page, state)
        await self._ensure_page_cte_matches(page, row, run_id, state, "antes de salvar")
        result = {}
        for attempt in range(2):
            await click_salvar_chamado(page)
            result = await wait_save_confirmation(page)
            if result.get("ok"):
                break
            missing = await inspect_required_fields(page)
            if attempt or not is_required_form_error(result):
                break
            await emit_warn(
                self.emit,
                run_id,
                "novelis.required_retry",
                f"Novelis indicou campo obrigatório ausente: {', '.join(missing.get('missing') or ['não identificado'])}.",
                {"result": result, "missing": missing},
            )
            if any(item in (missing.get("missing") or []) for item in ["PDF", "XML", "ZIP"]):
                await self._upload_files_if_present(page, row, config, run_id, state)
            await self._fill_title_message(page, row, config, run_id, state)
        if result.get("duplicate"):
            numero = str(result.get("numero") or "numero-nao-identificado")
            await emit_warn(
                self.emit,
                run_id,
                "novelis.chamado_exists",
                f"CTE já está cadastrado no chamado de número {numero}. Chamado não será aberto de novo.",
                {"row": row, "chamadoNumero": numero, "result": result, "ticket": ticket(row, numero)},
            )
            self._mark_processed(config, row, "ja_existia", numero)
            await update_novelis_overlay(
                page,
                {**state, "phase": "Ja existe", "message": f"CTE já cadastrado no chamado {numero}. Pulando."},
            )
            return
        if not result.get("ok"):
            message = str(result.get("message") or "Novelis não confirmou o salvamento.")
            await update_novelis_overlay(page, {**state, "phase": "Erro ao salvar", "message": message})
            raise RuntimeError(message)
        numero = str(result.get("numero") or "").strip()
        message = f"Chamado salvo no Novelis{f': {numero}' if numero else ''}."
        await emit_step(self.emit, run_id, "novelis.save", message,
                        {"numeroChamado": numero, "result": result, "ticket": ticket(row, numero)})
        self._mark_processed(config, row, "aberto", numero)
        await update_novelis_overlay(page, {**state, "phase": "Concluido", "message": message})

    async def _novelis_page(self, browser: BrowserDriver, force_new: bool = False) -> Page:
        page = None if force_new else await browser.find_page_by_url("novelis")
        if page is None:
            page = await browser.new_page()
        return await browser.focus_page(page)

    def _overlay_state(self, row: dict[str, Any]) -> dict[str, str]:
        parts = [str(row.get(key) or "").strip() for key in ("filial", "serie", "documento")]
        numero_cte = "-".join(parts) if all(parts) else str(row.get("numeroCte") or row.get("cte") or "")
        return {"cte": numero_cte}

    async def _ensure_page_cte_matches(
        self,
        page: Page,
        row: dict[str, Any],
        run_id: str,
        state: dict[str, Any],
        stage: str,
    ) -> None:
        expected = self._expected_cte(row)
        detected = await self._detect_page_cte(page)
        if not expected or not detected or self._cte_key(expected) == self._cte_key(detected):
            return
        message = (
            f"Tela Novelis abriu CTE {detected}, mas o fluxo estava em {expected}. "
            "Salvamento bloqueado."
        )
        await emit_warn(
            self.emit,
            run_id,
            "novelis.cte_mismatch",
            message,
            {"expected": expected, "detected": detected, "url": page.url, "stage": stage},
        )
        await update_novelis_overlay(page, {**state, "phase": "Divergencia", "message": message})
        raise RuntimeError(message)

    async def _detect_page_cte(self, page: Page) -> str:
        return await detect_page_cte(page)

    def _expected_cte(self, row: dict[str, Any]) -> str:
        parts = [row.get("filial"), row.get("serie"), row.get("documento")]
        cte = "-".join(str(part).strip() for part in parts if str(part or "").strip())
        return cte or str(row.get("numeroCte") or "")

    def _cte_key(self, value: Any) -> str:
        parts = re.findall(r"\d+", str(value or ""))
        if len(parts) < 3:
            return ""
        return "|".join(str(int(part)) for part in parts[:3])

    def _documento_key(self, value: Any) -> str:
        digits = re.sub(r"\D+", "", str(value or ""))
        return digits.lstrip("0") or digits

    def _list_documentos(self, rows: list[dict[str, Any]]) -> str:
        docs = [str(row.get("documento") or "").strip() for row in rows if isinstance(row, dict)]
        return ", ".join(doc for doc in docs if doc) or "nenhum"
