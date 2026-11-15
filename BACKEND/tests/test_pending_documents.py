from types import SimpleNamespace

from app.services.pending_documents import refresh_files


def test_live_queue_rechecks_creation_deletion_and_exact_fiscal_identity(tmp_path):
    pdf, xml, proofs = [tmp_path / name for name in ("pdf", "xml", "proofs")]
    for directory in (pdf, xml, proofs):
        directory.mkdir()
    config = SimpleNamespace(
        get=lambda key: "false",
        rodopar_pdf=lambda: {"downloadTargetDir": str(pdf)},
        xml_sefaz=lambda: {"downloadDir": str(xml)},
        comprovante_local=lambda: {"targetDir": str(proofs)},
    )
    rows = [
        {"filial": branch, "serie": 10, "documento": 7, "cteId": str(branch)[0] * 44}
        for branch in (1, 11)
    ]
    rows[1]["cteId"] = "2" * 44
    plan = {"checked": [{"cte": f"{row['filial']}-10-7", "row": row} for row in rows]}
    assert refresh_files(plan, config, tmp_path)["faltandoPdf"] == ["1-10-7", "11-10-7"]
    (pdf / "CTE_11-10-7.pdf").write_bytes(b"%PDF-valid")
    target = xml / "CTE_11-10-7.xml"
    content = (
        '<cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe>'
        f'<infCte Id="CTe{rows[1]["cteId"]}"><ide><serie>10</serie><nCT>7</nCT>'
        "</ide></infCte></CTe></cteProc>"
    )
    target.write_text(content)
    checked = refresh_files(plan, config, tmp_path)
    assert checked["faltandoPdf"] == checked["faltandoXml"] == ["1-10-7"]
    assert checked["prontosChamado"] == ["11-10-7"]
    assert all(not item.get("evidence") for item in plan["checked"])
    target.unlink()
    assert refresh_files(plan, config, tmp_path)["faltandoXml"] == ["1-10-7", "11-10-7"]
    target.write_text(content.replace(rows[1]["cteId"], "3" * 44))
    assert refresh_files(plan, config, tmp_path)["prontosChamado"] == []


def test_shared_folder_access_error_is_reported_instead_of_false_missing(tmp_path, monkeypatch):
    import pytest

    from app.services.document_index import DocumentIndex

    def inaccessible(*args):
        raise PermissionError("fixture")

    monkeypatch.setattr("app.services.document_index.os.scandir", inaccessible)
    with pytest.raises(PermissionError):
        DocumentIndex().files(tmp_path, {".pdf"})


def test_network_reads_for_distinct_cte_directories_can_run_concurrently(tmp_path, monkeypatch):
    import os
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.services.document_index import DocumentIndex

    folders = [tmp_path / name for name in ("cte-1", "cte-2")]
    for folder in folders:
        folder.mkdir()
        (folder / "test.pdf").write_bytes(b"%PDF-test")
    rendezvous = Barrier(2, timeout=3)
    scan = os.scandir

    def slow_network(directory):
        rendezvous.wait()
        return scan(directory)

    monkeypatch.setattr("app.services.document_index.os.scandir", slow_network)
    index = DocumentIndex()
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(lambda folder: index.files(folder, {".pdf"}), folders))
    assert all(len(files) == 1 for files in results)
