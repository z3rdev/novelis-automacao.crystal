import json
import re
from pathlib import Path
from typing import Any
from playwright.async_api import Page
from app.automation.flows.flow_events import emit_warn
from app.automation.flows.novelis_chamados.overlay.novelis_overlay import update_novelis_overlay
from app.data.chamados_log import mark_cte_processed
from app.data.chamados_reader import find_chamado_for_cte
from app.infrastructure.json_store import read_json
from app.services.chamado_message import DEFAULT_COMPLEMENT, DEFAULT_MESSAGE, render_message
from app.services.execution_reports.models import ticket


class NovelisSupport:
    def build_chamado_message(self, data, assinatura, template=None):
        default = DEFAULT_COMPLEMENT if self._is_complementar(data) else DEFAULT_MESSAGE
        return render_message(data, assinatura, template or default)

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
            {"row": row, "chamadoNumero": numero, "ticket": ticket(row, numero)},
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
        from app.services.chamados_catalog import current_catalog
        if catalog := current_catalog(self.cwd):
            catalog.record_processed(row, status, numero)
            return
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
