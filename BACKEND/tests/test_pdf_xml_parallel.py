import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.automation.flows.pendentes.controles.pdf_xml_parallel import PdfXmlParallelRunner
from app.domain.models import RunStartRequest


async def emit_stub(*args, **kwargs):
    return None


def test_pdf_xml_runner_starts_pdf_and_xml_together():
    events, result, labels = asyncio.run(_parallel_scenario())

    assert set(events[:2]) == {"pdf-start", "xml-start"}
    assert set(events[-2:]) == {"pdf-end", "xml-end"}
    assert result["refreshed"] == "Depois do PDF/Sefaz"
    assert labels == ["Depois do PDF/Sefaz"]


async def _parallel_scenario():
    events: list[str] = []
    labels: list[str] = []
    pdf_started = asyncio.Event()
    xml_started = asyncio.Event()
    plan = {
        "faltandoPdf": ["2-10-10402"],
        "faltandoXml": ["2-10-10402"],
    }

    async def run_pdf(*args):
        events.append("pdf-start")
        pdf_started.set()
        await asyncio.wait_for(xml_started.wait(), timeout=1)
        events.append("pdf-end")

    async def run_xml(*args):
        events.append("xml-start")
        xml_started.set()
        await asyncio.wait_for(pdf_started.wait(), timeout=1)
        events.append("xml-end")

    async def refresh_plan(*args):
        label = args[-1]
        labels.append(label)
        return {**plan, "refreshed": label}

    runner = PdfXmlParallelRunner(
        SimpleNamespace(),
        emit_stub,
        run_pdf,
        run_xml,
        refresh_plan,
    )
    result = await runner.run(
        None,
        {},
        {},
        {},
        plan,
        RunStartRequest(flow="pendentes", dry_run=False),
        "run-parallel",
        {},
        Path("plan.json"),
    )
    return events, result, labels
