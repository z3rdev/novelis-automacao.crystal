import json
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
from app.data.chamados_log import mark_cte_processed
from app.data.chamados_reader import find_chamado_for_cte
from app.infrastructure.json_store import read_json
from app.services.browser_driver import BrowserDriver


class NovelisFlow:
    def __init__(self, cwd: Path, emit: Emit) -> None:
        self.cwd = cwd
        self.emit = emit

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

        if browser is None:
            raise RuntimeError("BrowserDriver obrigatório para Novelis real.")
        page = await self._novelis_page(browser, force_new=False)
        completed = False
        try:
            await self.run_chamado_flow(page, config, run_id)
            completed = True
        finally:
            if completed and config.get("chamadoClosePage", False):
                await page.close()
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

        await self.ensure_portal_authenticated(page, config, run_id, state)
        await emit_step(self.emit, run_id, "novelis.open_chamado", "Abrindo tela de chamado.")
        page = await self._open_chamado_screen(page, config, state)
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
        login_url = self._required_url(config, "loginUrl", "NOVELIS_LOGIN_URL", "portalUrl")
        await emit_step(self.emit, run_id, "novelis.login", "Abrindo portal Novelis.")
        await page.goto(login_url, wait_until="domcontentloaded")
        if state:
            await update_novelis_overlay(
                page,
                {
                    **state,
                    "phase": "Login",
                    "message": "Verificando login no portal Novelis.",
                },
            )
            await wait_if_novelis_paused(page, state)
        if not await self._is_visible(page, 'input[type="password"]', timeout=5_000):
            return
        if state:
            await update_novelis_overlay(
                page,
                {
                    **state,
                    "phase": "Login",
                    "message": "Preenchendo usuário e senha no portal Novelis.",
                },
            )
        await page.locator('input[type="email"], input[name="email"], #email').first.fill(str(config.get("user") or ""))
        await page.locator('input[type="password"]').first.fill(str(config.get("pass") or ""))
        await page.locator('button[type="submit"], input[type="submit"]').first.click()
        await page.wait_for_timeout(2500)
        if state:
            await update_novelis_overlay(
                page,
                {
                    **state,
                    "phase": "Login",
                    "message": "Login enviado. Continuando para abertura do chamado.",
                },
            )

    async def _select_item(self, page: Page, item_text: str) -> None:
        await select_chamado_item(page, item_text)

    async def _open_chamado_screen(self, page: Page, config: dict[str, Any], state: dict[str, Any]) -> Page:
        if config.get("chamadoPreferDirectUrl", True):
            direct_url = self._direct_chamado_url(config)
            if not direct_url:
                raise RuntimeError("Configure NOVELIS_CHAMADO_DIRETO_URL ou NOVELIS_PORTAL_URL para abrir chamado.")
            await update_novelis_overlay(
                page,
                {**state, "phase": "Abrindo chamado", "message": "Abrindo chamado pela URL direta."},
            )
            await wait_if_novelis_paused(page, state)
            await page.goto(direct_url, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)
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
        await page.goto(chamado_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
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
        numero_cte = "-".join(part for part in [row.get("filial"), row.get("serie"), row.get("documento")] if part)
        title = f"CTE {numero_cte}" if numero_cte else str(config.get("chamadoTitulo") or "AUDITORIA DE FRETE")
        message = self.build_chamado_message(row, str(config.get("chamadoAssinatura") or ""))
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
                {"row": row, "chamadoNumero": numero, "result": result},
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
        await emit_step(self.emit, run_id, "novelis.save", message, {"numeroChamado": numero, "result": result})
        self._mark_processed(config, row, "aberto", numero)
        await update_novelis_overlay(page, {**state, "phase": "Concluido", "message": message})

    async def _novelis_page(self, browser: BrowserDriver, force_new: bool = False) -> Page:
        page = None if force_new else await browser.find_page_by_url("novelis")
        if page is None:
            page = await browser.new_page()
        return await browser.focus_page(page)

    def _overlay_state(self, row: dict[str, Any]) -> dict[str, str]:
        numero_cte = "-".join(part for part in [row.get("filial"), row.get("serie"), row.get("documento")] if part)
        return {"cte": numero_cte or str(row.get("numeroCte") or "")}

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

    def build_chamado_message(self, data: dict[str, Any], assinatura: str) -> str:
        numero_cte = "-".join(part for part in [data.get("filial"), data.get("serie"), data.get("documento")] if part)
        rota = data.get("rota") or f"{data.get('remCidade', '')} x {data.get('desCidade', '')}".strip()
        intro = "SEGUE O CTE COMPLEMENTAR, ACOMPANHADO DO XML E DO TARIFARIO CORRESPONDENTE."
        if not self._is_complementar(data):
            intro = "SEGUE O CTE, ACOMPANHADO DO XML E DO TARIFARIO CORRESPONDENTE."
        lines = [
            "PREZADOS,",
            "",
            intro,
            "",
            f"PERCURSO {data.get('percurso') or ''}",
            f"TON: {data.get('ton') or data.get('tonRaw') or ''}",
            f"ID: {data.get('id') or ''}",
            f"ID TARIFARIO: {data.get('idTarifario') or ''}",
            f"ROTA: {rota}",
            f"N DO CTE: {numero_cte}",
        ]
        if self._is_complementar(data):
            lines.append(f"N CTE DE ORIGEM: {data.get('cteOrigem') or ''}")
            lines.append(f"N DO CHAMADO: {data.get('chamadoOrigem') or ''}")
        lines.extend(["", "Att,", assinatura])
        return "\n".join(lines)

    def _resolve_tarifario_row(self, config: dict[str, Any]) -> dict[str, Any]:
        payload = read_json(self._resolve(config.get("tarifarioOutputFile") or ""), {})
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            return {}
        wanted = self._documento_key(config.get("currentDocumento") or config.get("documentoFilter"))
        if not wanted:
            return rows[0]
        for row in rows:
            if isinstance(row, dict) and self._documento_key(row.get("documento")) == wanted:
                return row
        raise RuntimeError(
            f"Resultado do tarifário não contém o CTE esperado {wanted}. "
            f"Encontrado(s): {self._list_documentos(rows)}. Fluxo bloqueado para evitar usar outro CTE."
        )

    async def _skip_if_chamado_already_exists(
        self,
        page: Page,
        config: dict[str, Any],
        row: dict[str, Any],
        run_id: str,
        state: dict[str, Any],
    ) -> bool:
        numero = await self._detect_existing_chamado_banner(page)
        if not numero:
            return False
        await emit_warn(
            self.emit,
            run_id,
            "novelis.chamado_exists",
            f"CTE já está cadastrado no chamado de número {numero}. Chamado não será aberto de novo.",
            {"row": row, "chamadoNumero": numero},
        )
        self._mark_processed(config, row, "ja_existia", numero)
        await update_novelis_overlay(
            page,
            {
                **state,
                "phase": "Ja existe",
                "message": f"CTE já cadastrado no chamado {numero}. Pulando.",
            },
        )
        return True

    async def _detect_existing_chamado_banner(self, page: Page) -> str | None:
        try:
            locator = page.get_by_text(re.compile(r"j[aá] est[aá] cadastrado no chamado", re.IGNORECASE)).first
            if not await locator.is_visible(timeout=2_000):
                return None
            text = await locator.inner_text()
        except Exception:
            return None
        match = re.search(r"(\d{6,})", text)
        return match.group(1) if match else "numero-nao-identificado"

    def _mark_processed(self, config: dict[str, Any], row: dict[str, Any], status: str, numero: str) -> None:
        log_file = config.get("chamadosLogFile")
        if not log_file:
            return
        try:
            mark_cte_processed(
                Path(str(log_file)),
                row.get("filial"),
                row.get("serie"),
                row.get("documento"),
                status,
                numero,
                row.get("cteId") or "",
            )
        except Exception:
            pass

    def _find_existing_chamado(
        self,
        config: dict[str, Any],
        row: dict[str, Any],
    ) -> dict[str, Any] | None:
        chamados_hit = find_chamado_for_cte(
            self.cwd,
            config.get("relatorioCteXmlJsonFile"),
            row.get("filial"),
            row.get("serie"),
            row.get("documento"),
            config.get("chamadosSnapshotFile"),
            row.get("cteId"),
        )
        if chamados_hit:
            return {"chamadoNumero": chamados_hit.get("chamado")}

        lista_file = config.get("listaJsonFile") or config.get("listaOutputFile")
        if not lista_file:
            return None
        payload = read_json(self._resolve(lista_file), {})
        rows = payload.get("rows") or payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return None
        target = self._digits(row.get("documento"))
        for item in rows:
            text = json.dumps(item, ensure_ascii=False)
            if target and target in self._digits(text):
                return item
        return None

    async def _is_visible(self, page: Page, selector: str, timeout: int = 3_000) -> bool:
        return await self._locator_visible(page.locator(selector).first, timeout)

    async def _locator_visible(self, locator, timeout: int = 3_000) -> bool:
        try:
            return await locator.is_visible(timeout=timeout)
        except Exception:
            return False

    def _is_complementar(self, data: dict[str, Any]) -> bool:
        if data.get("isCteComplementarFrete"):
            return True
        return bool(re.search(r"CTE\s+COMPLEMENTAR\s+DE\s+FRETE", str(data.get("observacao") or ""), re.I))

    def _digits(self, value: Any) -> str:
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    def _int(self, value: Any, fallback: int) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return fallback

    def _resolve(self, value: str) -> Path:
        path = Path(str(value or ""))
        return path if path.is_absolute() else self.cwd / path

    def _required_url(self, config: dict[str, Any], key: str, env_key: str, *fallback_keys: str) -> str:
        value = str(config.get(key) or "").strip()
        for fallback_key in fallback_keys:
            value = value or str(config.get(fallback_key) or "").strip()
        if not value:
            raise RuntimeError(f"Configure {env_key} no BACKEND/.env para abrir o Novelis.")
        return value

    def _direct_chamado_url(self, config: dict[str, Any]) -> str:
        configured = str(config.get("chamadoDiretoUrl") or "").strip()
        if configured:
            return configured
        portal = str(config.get("portalUrl") or "").strip().rstrip("/")
        return f"{portal}/chamado/" if portal else ""
