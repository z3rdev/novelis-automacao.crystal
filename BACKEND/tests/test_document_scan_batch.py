import asyncio
import os
from collections import Counter
from threading import Barrier
from unittest.mock import AsyncMock

import pytest

from app.automation.cancellation import RunCancellation, RunCancelled, cancellation_scope
from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
from app.services.cte_xml_files import matching_xml_files
from app.services.document_scan import scan_evidence


def roots(tmp_path):
    directories = [tmp_path / name for name in ("pdf", "xml", "proofs")]
    for directory in directories:
        directory.mkdir()
    return directories


def test_automation_scans_each_root_once_and_skips_nonexistent_child_folders(tmp_path, monkeypatch):
    pdf, xml, proofs = roots(tmp_path)
    row = {"filial": "8", "serie": "10", "documento": "1559", "cteId": "2" * 44}
    (pdf / "CTE_8-10-1559.pdf").write_bytes(b"%PDF-valid")
    (xml / "CTE_8-10-1559.xml").write_text(
        '<cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe><infCte Id="CTe'
        + "2" * 44
        + '"><ide><serie>10</serie><nCT>1559</nCT></ide></infCte></CTe></cteProc>'
    )
    calls = Counter()
    scan = os.scandir

    def tracked(directory):
        calls[str(directory)] += 1
        return scan(directory)

    monkeypatch.setattr("app.services.document_index.os.scandir", tracked)
    builder = PendentesPlanBuilder(tmp_path, AsyncMock())
    _, checked = builder._filter_and_check_rows(
        [row],
        None,
        {},
        {"downloadTargetDir": str(pdf)},
        {"downloadDir": str(xml)},
        {"targetDir": str(proofs)},
        explicit_xml=True,
    )
    assert checked[0]["evidence"]["pdfFile"].endswith("CTE_8-10-1559.pdf")
    assert checked[0]["evidence"]["xmlFile"].endswith("CTE_8-10-1559.xml")
    assert calls == Counter({str(directory): 1 for directory in (pdf, xml, proofs)})


def test_batch_roots_and_rows_run_concurrently_without_changing_row_order(tmp_path):
    pdf, xml, proofs = roots(tmp_path)
    root_barrier, row_barrier = Barrier(3, timeout=3), Barrier(3, timeout=3)
    builder = PendentesPlanBuilder(tmp_path, None)

    def list_files(*args):
        root_barrier.wait()
        return []

    def evidence(row, *args):
        row_barrier.wait()
        return {"identity": row["documento"]}

    builder._all_files, builder.resolve_evidence = list_files, evidence
    result = scan_evidence(
        builder,
        [{"documento": value} for value in (3, 1, 2)],
        {"downloadTargetDir": str(pdf)},
        {"downloadDir": str(xml)},
        {"targetDir": str(proofs)},
    )
    assert [item["identity"] for item in result] == [3, 1, 2]


def test_cancellation_context_reaches_file_workers_before_any_directory_io(tmp_path):
    builder = PendentesPlanBuilder(tmp_path, None)
    builder._all_files = lambda *args: pytest.fail("Cancelled scan accessed the filesystem")

    async def exercise():
        control = RunCancellation()
        control.request_cancel()
        with cancellation_scope(control), pytest.raises(RunCancelled):
            await asyncio.to_thread(scan_evidence, builder, [{"documento": 1}], {}, {}, {})

    asyncio.run(exercise())


def test_first_valid_xml_avoids_scanning_unneeded_legacy_directory(tmp_path):
    row = {"filial": 8, "serie": 10, "documento": 1559, "cteId": "2" * 44}
    canonical = tmp_path / "CTE_8-10-1559.xml"
    canonical.write_text(
        '<cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe><infCte Id="CTe'
        + "2" * 44
        + '"><ide><serie>10</serie><nCT>1559</nCT></ide></infCte></CTe></cteProc>'
    )

    def listing(directory, extensions):
        assert directory == tmp_path
        return [canonical]

    assert matching_xml_files(tmp_path, row, files=listing, first_only=True) == [canonical]
    canonical.write_text("<html>invalid</html>")
    legacy = tmp_path / "cte-1559"
    legacy.mkdir()
    archived = legacy / ("2" * 44 + ".xml")
    archived.write_text(
        '<CTe xmlns="http://www.portalfiscal.inf.br/cte"><infCte Id="CTe'
        + "2" * 44
        + '"><ide><serie>10</serie><nCT>1559</nCT></ide></infCte></CTe>'
    )
    assert matching_xml_files(tmp_path, row, first_only=True) == [archived]
