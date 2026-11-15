from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from chat_storage_fake import MemoryS3

from app.domain.chat import ChatStorageError
from app.services.chat_files import ChatFiles
from app.services.chat_storage import ARCHIVE, ChatObjectStorage


def test_retention_is_scoped_and_preserves_other_bucket_rules():
    client = MemoryS3()
    other = {
        "ID": "unrelated",
        "Status": "Enabled",
        "Filter": {"Prefix": "another-app/"},
        "Expiration": {"Days": 90},
    }
    client.lifecycle = [other]
    storage = ChatObjectStorage(Path(), SimpleNamespace(), client)
    rule = storage.ensure_retention()
    assert rule["Filter"] == {"Prefix": ARCHIVE} and rule["Expiration"] == {"Days": 30}
    assert client.lifecycle == [other, rule]
    storage.ensure_retention()
    assert client.lifecycle == [other, rule]


def test_failed_minio_upload_never_creates_a_network_copy(tmp_path, monkeypatch):
    client = MemoryS3()
    storage = ChatObjectStorage(tmp_path, SimpleNamespace(), client)
    files = ChatFiles(tmp_path / "network", storage)
    metadata = {"kind": "guia", "id": str(uuid4()), "sha256": sha256(b"data").hexdigest()}
    monkeypatch.setattr(
        client, "put_object", lambda **kwargs: (_ for _ in ()).throw(OSError("controlled"))
    )
    with pytest.raises(ChatStorageError):
        files.write("11-10-433", metadata, b"data")
    assert not (tmp_path / "network").exists()


def test_document_read_is_limited_to_the_cte_prefix():
    storage = ChatObjectStorage(Path(), SimpleNamespace(), MemoryS3())
    with pytest.raises(ChatStorageError, match="Endereço"):
        storage.read(
            "11-10-433", {"object_key": "cargo-hub/gnre/pending/1-10-433/doc.pdf", "sha256": "a"}
        )


def test_minio_metadata_header_case_does_not_reject_valid_objects(monkeypatch):
    client = MemoryS3()
    storage = ChatObjectStorage(Path(), SimpleNamespace(), client)
    head = client.head_object

    def mixed_case(**kwargs):
        value = head(**kwargs)
        value["Metadata"] = {key.upper(): item for key, item in value["Metadata"].items()}
        return value

    monkeypatch.setattr(client, "head_object", mixed_case)
    metadata = {"kind": "guia", "id": str(uuid4()), "sha256": sha256(b"pdf").hexdigest()}
    storage.write("11-10-433", metadata, b"pdf")
    assert storage.read("11-10-433", metadata) == b"pdf"


def test_unified_network_delivery_is_recognized_by_plan_and_zip(tmp_path):
    import io
    import zipfile

    from pypdf import PdfReader, PdfWriter

    from app.automation.flows.novelis_chamados.controles.evidence import _build_zip
    from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
    from app.services.chat_files import MANIFEST, merge_pdfs
    from app.services.chat_network import ChatNetworkDelivery

    files = ChatFiles(
        tmp_path / "network", ChatObjectStorage(tmp_path, SimpleNamespace(), MemoryS3())
    )
    stream, writer = io.BytesIO(), PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(stream)
    row = {"cte": "11-10-433", "generation": uuid4()}
    for kind, data in (
        ("guia", stream.getvalue()),
        ("comprovante", stream.getvalue()),
        ("combined", merge_pdfs(stream.getvalue(), stream.getvalue())),
    ):
        metadata = {"kind": kind, "id": str(uuid4()), "sha256": sha256(data).hexdigest()}
        files.write(row["cte"], metadata, data)
        row[kind] = metadata
    files.publish(row)
    directory = files.directory(row["cte"])
    assert {path.name for path in directory.iterdir()} == {MANIFEST, "GNR_CMP_11-10-433.pdf"}
    fiscal = {"filial": "11", "serie": "10", "documento": "433", "NMGNRE": "123"}
    evidence = PendentesPlanBuilder(tmp_path, None).resolve_evidence(
        fiscal, {}, {}, {"sourceDir": str(files.root)}
    )
    assert evidence["comprovanteOk"] is True
    assert len(evidence["comprovanteFiles"]) == len(evidence["comprovanteZipFiles"]) == 1
    xml = tmp_path / "CTE_11-10-433.xml"
    xml.write_text("<controlled-fixture/>")
    output = _build_zip(
        tmp_path,
        {"chamadoZipDir": str(tmp_path / "zip")},
        fiscal,
        xml,
        [directory / "GNR_CMP_11-10-433.pdf"],
    )
    with zipfile.ZipFile(output) as zipped:
        assert len(PdfReader(io.BytesIO(zipped.read("GNR_CMP_11-10-433.pdf"))).pages) == 2
    unrelated = directory / "manual.txt"
    unrelated.write_text("preserve")
    ChatNetworkDelivery(files).cleanup(row)
    assert list(directory.iterdir()) == [unrelated]
