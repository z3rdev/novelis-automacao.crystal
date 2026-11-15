import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.config.settings import Settings
from app.domain.models import RunStartRequest
from app.services.browser_driver import BrowserDriver


RunPdf = Callable[
    [BrowserDriver | None, dict[str, Any], dict[str, Any], RunStartRequest, str, dict[str, Any]],
    Awaitable[None],
]
RunXmlSefaz = Callable[
    [BrowserDriver | None, dict[str, Any], dict[str, Any], RunStartRequest, str, dict[str, Any], Path],
    Awaitable[None],
]
RefreshPlan = Callable[
    [dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], RunStartRequest, str, str],
    Awaitable[dict[str, Any]],
]


class PdfXmlParallelRunner:
    def __init__(
        self,
        settings: Settings,
        emit: Emit,
        run_pdf: RunPdf,
        run_xml_sefaz: RunXmlSefaz,
        refresh_plan: RefreshPlan,
    ) -> None:
        self.settings = settings
        self.emit = emit
        self.run_pdf = run_pdf
        self.run_xml_sefaz = run_xml_sefaz
        self.refresh_plan = refresh_plan

    async def run(
        self,
        browser: BrowserDriver | None,
        rodopar_config: dict[str, Any],
        xml_config: dict[str, Any],
        comprovante_config: dict[str, Any],
        plan: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        config: dict[str, Any],
        plan_file: Path,
    ) -> dict[str, Any]:
        run_pdf = not config.get("skipPdf")
        run_xml = not config.get("skipXml")
        if "faltandoPdf" in plan and "faltandoXml" in plan and not plan["faltandoPdf"] and not plan["faltandoXml"]:
            if run_pdf:
                await self.run_pdf(browser, rodopar_config, plan, request, run_id, config)
            if run_xml:
                await self.run_xml_sefaz(browser, xml_config, plan, request, run_id, config, plan_file)
            return plan
        if run_pdf and run_xml:
            return await self._run_parallel(
                browser,
                rodopar_config,
                xml_config,
                comprovante_config,
                plan,
                request,
                run_id,
                config,
                plan_file,
            )
        if run_pdf:
            await self.run_pdf(browser, rodopar_config, plan, request, run_id, config)
            return await self._refresh(config, rodopar_config, xml_config, comprovante_config, request, run_id, "Depois do PDF")
        if run_xml:
            await self.run_xml_sefaz(browser, xml_config, plan, request, run_id, config, plan_file)
            return await self._refresh(config, rodopar_config, xml_config, comprovante_config, request, run_id, "Depois da Sefaz")
        return plan

    async def _run_parallel(
        self,
        browser: BrowserDriver | None,
        rodopar_config: dict[str, Any],
        xml_config: dict[str, Any],
        comprovante_config: dict[str, Any],
        plan: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        config: dict[str, Any],
        plan_file: Path,
    ) -> dict[str, Any]:
        await emit_step(
            self.emit,
            run_id,
            "pendentes.pdf_xml_parallel",
            f"PDF {config.get('pdfSource', 'crystal')} e XML Sefaz iniciados simultaneamente.",
            {
                "faltandoPdf": plan.get("faltandoPdf", []),
                "faltandoXml": plan.get("faltandoXml", []),
            },
        )
        xml_browser = BrowserDriver(self.settings) if browser is not None else None
        if browser is not None:
            browser.preview_override = xml_browser
        try:
            stages = [
                (
                    "PDF",
                    asyncio.create_task(
                        self.run_pdf(browser, rodopar_config, plan, request, run_id, config)
                    ),
                ),
                (
                    "XML Sefaz",
                    asyncio.create_task(
                        self.run_xml_sefaz(xml_browser or browser, xml_config, plan, request, run_id, config, plan_file)
                    ),
                ),
            ]
            results = await asyncio.gather(*(task for _, task in stages), return_exceptions=True)
        finally:
            if xml_browser is not None:
                await xml_browser.close()
            if browser is not None:
                browser.preview_override = None

        errors = [(name, result) for (name, _task), result in zip(stages, results) if isinstance(result, Exception)]
        if errors:
            refreshed = await self._refresh(
                config,
                rodopar_config,
                xml_config,
                comprovante_config,
                request,
                run_id,
                "Depois do PDF/Sefaz parcial",
            )
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.pdf_xml_parallel_error",
                self._error_message(errors),
                {"errors": [{"stage": name, "message": str(error)} for name, error in errors]},
            )
            raise RuntimeError(self._error_message(errors)) from errors[0][1]

        refreshed = await self._refresh(
            config,
            rodopar_config,
            xml_config,
            comprovante_config,
            request,
            run_id,
            "Depois do PDF/Sefaz",
        )
        await emit_step(
            self.emit,
            run_id,
            "pendentes.pdf_xml_parallel_done",
            "PDF e XML Sefaz concluidos.",
            {
                "faltandoPdf": refreshed.get("faltandoPdf", []),
                "faltandoXml": refreshed.get("faltandoXml", []),
            },
        )
        return refreshed

    async def _refresh(
        self,
        config: dict[str, Any],
        rodopar_config: dict[str, Any],
        xml_config: dict[str, Any],
        comprovante_config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        label: str,
    ) -> dict[str, Any]:
        return await self.refresh_plan(
            config,
            rodopar_config,
            xml_config,
            comprovante_config,
            request,
            run_id,
            label,
        )

    def _error_message(self, errors: list[tuple[str, BaseException]]) -> str:
        detail = "; ".join(f"{name}: {error}" for name, error in errors)
        return f"PDF/XML simultaneos falharam: {detail}"
