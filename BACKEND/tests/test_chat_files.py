import io
import json
from uuid import uuid4

import pytest
from pypdf import PdfReader, PdfWriter

from app.domain.chat import ChatError, GnreRequestInput
from app.services.chat_files import ChatFiles, pdf_bytes, merge_pdfs, published_documents


def pdf(width=100):
    stream, writer = io.BytesIO(), PdfWriter()
    writer.add_blank_page(width=width, height=100)
    writer.write(stream)
    return stream.getvalue()


def test_pdf_and_image_inputs_are_validated(monkeypatch):
    from PIL import Image, PdfImagePlugin
    import time

    assert pdf_bytes(pdf(), "arquivo.pdf").startswith(b"%PDF-")
    image = io.BytesIO()
    Image.new("RGB", (10, 10)).save(image, "PNG")
    first = pdf_bytes(image.getvalue(), "imagem.png")
    monkeypatch.setattr(
        PdfImagePlugin.time, "gmtime", lambda: time.struct_time((2030, 1, 1, 0, 0, 0, 1, 1, 0))
    )
    assert pdf_bytes(image.getvalue(), "imagem.png") == first
    assert len(PdfReader(io.BytesIO(first)).pages) == 1
    with pytest.raises(ChatError):
        pdf_bytes(b"not a PDF", "arquivo.pdf")
    with pytest.raises(ChatError):
        pdf_bytes(b"", "arquivo.pdf")
    assert len(PdfReader(io.BytesIO(merge_pdfs(pdf(), pdf(200)))).pages) == 2


def test_full_cte_identity_and_manifest_paths(tmp_path):
    from hashlib import sha256

    files, data = ChatFiles(tmp_path), pdf()
    metadata = {"id": str(uuid4()), "kind": "guia", "sha256": sha256(data).hexdigest()}
    files.write("10-10-2789", metadata, data)
    files.publish({"cte": "10-10-2789", "guia": metadata, "generation": uuid4()})
    assert files.read("10-10-2789", metadata) == data
    assert published_documents(tmp_path, "10-10-2789")["guia"].name == "GNR_10-10-2789.pdf"
    assert published_documents(tmp_path, "11-10-2789") == {}
    assert published_documents(tmp_path, "invalid") == {}
    with pytest.raises(ValueError):
        GnreRequestInput(cte="../outside")
    manifest = tmp_path / "10-10-2789/.cargo-hub-documents.json"
    malicious = {
        "schema": 1,
        "cte": "10-10-2789",
        "files": {"guia": {"relative_path": "../../outside.pdf"}},
    }
    manifest.write_text(json.dumps(malicious))
    assert published_documents(tmp_path, "10-10-2789") == {}


def test_managed_versions_are_not_mixed_with_current_documents(tmp_path):
    from hashlib import sha256
    from app.automation.flows.comprovantes_locais.steps.comprovante_local import (
        ComprovanteLocalFlow,
    )

    files, data = ChatFiles(tmp_path), pdf()
    current = {"id": str(uuid4()), "kind": "guia", "sha256": sha256(data).hexdigest()}
    older = {**current, "id": str(uuid4())}
    files.write("10-10-2789", older, data)
    files.write("10-10-2789", current, data)
    files.publish({"cte": "10-10-2789", "guia": current, "generation": uuid4()})
    found = ComprovanteLocalFlow(tmp_path, None)._list_files(tmp_path)
    assert found == [files.path("10-10-2789", current)]


def test_receipt_bundle_is_found_and_merged_pdf_is_added_to_the_zip(tmp_path):
    import zipfile
    from hashlib import sha256
    from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
    from app.automation.flows.novelis_chamados.controles.evidence import _build_zip

    files, guia, proof = ChatFiles(tmp_path / "proofs"), pdf(), pdf(200)
    row = {"cte": "10-10-2789", "generation": uuid4()}
    for kind, data in (
        ("guia", guia),
        ("comprovante", proof),
        ("combined", merge_pdfs(guia, proof)),
    ):
        metadata = {"id": str(uuid4()), "kind": kind, "sha256": sha256(data).hexdigest()}
        files.write(row["cte"], metadata, data)
        row[kind] = metadata
    files.publish(row)
    fiscal = {"filial": "10", "serie": "10", "documento": "2789", "NMGNRE": "123"}
    evidence = PendentesPlanBuilder(tmp_path, None).resolve_evidence(
        fiscal, {}, {}, {"sourceDir": str(files.root)}
    )
    assert evidence["comprovanteOk"] is True
    assert len(evidence["comprovanteZipFiles"]) == 1
    xml = tmp_path / "CTE_10-10-2789.xml"
    xml.write_text("<controlled-unit-fixture/>")
    output = _build_zip(
        tmp_path,
        {"chamadoZipDir": str(tmp_path / "zip")},
        fiscal,
        xml,
        [files.path(row["cte"], row["combined"])],
    )
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {xml.name, "GNR_CMP_10-10-2789.pdf"}
        assert len(PdfReader(io.BytesIO(archive.read("GNR_CMP_10-10-2789.pdf"))).pages) == 2
    previous = output.read_bytes()
    files.path(row["cte"], row["combined"]).write_bytes(pdf(300))
    with pytest.raises(RuntimeError, match="Documento GNRE alterado"):
        _build_zip(
            tmp_path,
            {"chamadoZipDir": str(tmp_path / "zip")},
            fiscal,
            xml,
            [files.path(row["cte"], row["combined"])],
        )
    assert output.read_bytes() == previous
