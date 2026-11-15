from typing import Any

from app.automation.flows.comprovantes_locais.steps.comprovante_local import ComprovanteLocalFlow
from app.automation.flows.gnre.steps.gnre import GnreFlow
from app.automation.flows.novelis_chamados.steps.chamado_novelis import ChamadoNovelisFlow
from app.automation.flows.novelis_chamados.steps.novelis import NovelisFlow
from app.automation.flows.pendentes.steps.pendentes import PendentesFlow
from app.automation.flows.pre_passo.steps.pre_passo_legacy import PrePassoLegacyFlow
from app.automation.flows.rodopar_pdf_flow.steps.rodopar_pdf import RodoparPdfFlow
from app.automation.flows.sefaz_xml.steps.xml_sefaz import XmlSefazFlow
from app.automation.flows.tarifario.steps.tarifario import TarifarioFlow
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.domain.models import RunStartRequest
from app.infrastructure.event_bus import EventBus
from app.services.browser_driver import BrowserDriver
from app.services.rodopar_policy import LEGACY_RODOPAR_FLOWS, require_legacy_rodopar
from app.services.step_repository import StepRepository


class LegacyCoordinator:
    def __init__(
        self,
        settings: Settings,
        legacy_config: LegacyConfig,
        repository: StepRepository,
        event_bus: EventBus,
    ) -> None:
        self.settings = settings
        self.legacy_config = legacy_config
        self.repository = repository
        self.event_bus = event_bus

    async def run(
        self,
        request: RunStartRequest,
        run_id: str,
        browser: BrowserDriver | None,
    ) -> Any:
        flow_name = request.flow.strip().lower()
        if flow_name == "workflow":
            from app.automation.flows.scheduled_workflow.runner import ScheduledWorkflowRunner
            return await ScheduledWorkflowRunner(
                self.settings, self.legacy_config, self.repository, self.event_bus.publish
            ).run(browser, request, run_id)
        if flow_name in LEGACY_RODOPAR_FLOWS:
            require_legacy_rodopar(self.legacy_config)
        if flow_name == "pre-passo":
            return await self._pre().run_initial(browser, self.legacy_config.pre(), request, run_id)
        if flow_name == "tarifario":
            return await self._tarifario().run(browser, self.legacy_config.novelis(), request, run_id)
        if flow_name == "gnre":
            return await self._gnre().run(
                browser,
                self.legacy_config.gnre(),
                None,
                self.legacy_config.novelis().get("tarifarioOutputFile", ""),
                run_id,
                request.dry_run,
            )
        if flow_name == "novelis":
            return await self._novelis().run(browser, self.legacy_config.novelis(), request, run_id)
        if flow_name in {"rodopar-pdf", "pdf-rodopar"}:
            rodopar_config = self._rodopar_config(request)
            return await self._rodopar_pdf().run(
                browser,
                rodopar_config,
                request,
                run_id,
            )
        if flow_name == "xml-sefaz":
            return await self._xml_sefaz().run(
                browser,
                self.legacy_config.xml_sefaz(),
                request,
                run_id,
            )
        if flow_name == "buscar-chamados":
            from app.automation.flows.novelis_relatorio.steps.novelis_relatorio_cte_xml import NovelisRelatorioCteXmlFlow
            return await NovelisRelatorioCteXmlFlow(self.settings.backend_root.parent, self.event_bus.publish).run(
                browser, {**self.legacy_config.novelis(), "relatorioCteXmlSkipIfFreshToday": False}, [], run_id)
        if flow_name == "comprovante-local":
            return await self._comprovante_local().run(
                self.legacy_config.comprovante_local(),
                request,
                run_id,
            )
        if flow_name == "chamado-novelis":
            return await self._chamado_novelis().run(
                browser,
                self.legacy_config.chamado_novelis(),
                request,
                run_id,
            )
        if flow_name == "chamado-http":
            from app.automation.flows.novelis_chamados.steps.chamado_http import run_http_test
            return await run_http_test(self.settings, self.legacy_config, request, run_id, self.event_bus.publish)
        if flow_name in {"pendentes", "consulta-pendentes", "consulta"}:
            return await self._pendentes().run(browser, request, run_id)
        if flow_name == "integrado":
            return await self._run_integrado(browser, request, run_id)
        raise RuntimeError(f"Fluxo ainda não implementado: {request.flow}")

    def _rodopar_config(self, request: RunStartRequest) -> dict[str, Any]:
        config = self.legacy_config.rodopar_pdf()
        if request.rodopar_replay_overlay_enabled is not None:
            config = {**config, "replayOverlayEnabled": request.rodopar_replay_overlay_enabled}
        return config

    async def _run_integrado(
        self,
        browser: BrowserDriver | None,
        request: RunStartRequest,
        run_id: str,
    ) -> dict[str, Any]:
        pre_config = self.legacy_config.pre()
        novelis_config = self.legacy_config.novelis()
        gnre_config = self.legacy_config.gnre()

        data_par_page = await self._pre().run_initial(browser, pre_config, request, run_id)
        tarifario_rows = await self._tarifario().run(browser, novelis_config, request, run_id)
        first_row = tarifario_rows[0] if tarifario_rows else None
        gnre_file = None
        if gnre_config.get("enabled"):
            gnre_file = await self._gnre().run(
                browser,
                gnre_config,
                first_row,
                novelis_config.get("tarifarioOutputFile", ""),
                run_id,
                request.dry_run,
            )
        if browser is not None and data_par_page and pre_config.get("replayContinueAfterTarifario"):
            await self._pre().continue_after_tarifario(
                data_par_page,
                browser,
                pre_config,
                request,
                run_id,
            )
        await self._novelis().run(browser, novelis_config, request, run_id)
        return {"tarifarioRows": tarifario_rows, "gnreFile": gnre_file}

    def _pre(self) -> PrePassoLegacyFlow:
        return PrePassoLegacyFlow(self.settings, self.repository, self.event_bus.publish)

    def _tarifario(self) -> TarifarioFlow:
        return TarifarioFlow(self.legacy_config.cwd(), self.event_bus.publish)

    def _gnre(self) -> GnreFlow:
        return GnreFlow(self.legacy_config.cwd(), self.event_bus.publish)

    def _novelis(self) -> NovelisFlow:
        return NovelisFlow(self.legacy_config.cwd(), self.event_bus.publish)

    def _rodopar_pdf(self) -> RodoparPdfFlow:
        return RodoparPdfFlow(self.settings, self.repository, self.event_bus.publish)

    def _pendentes(self) -> PendentesFlow:
        return PendentesFlow(
            self.settings,
            self.legacy_config,
            self.repository,
            self.event_bus.publish,
        )

    def _xml_sefaz(self) -> XmlSefazFlow:
        return XmlSefazFlow(self.legacy_config.cwd(), self.event_bus.publish)

    def _comprovante_local(self) -> ComprovanteLocalFlow:
        return ComprovanteLocalFlow(self.legacy_config.cwd(), self.event_bus.publish)

    def _chamado_novelis(self) -> ChamadoNovelisFlow:
        from app.services.tariffs.audit import TariffAuditService
        return ChamadoNovelisFlow(self.legacy_config.cwd(), self.event_bus.publish, TariffAuditService(self.legacy_config))
