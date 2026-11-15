import os
from pathlib import Path

import pytest

from app.services.document_index import DocumentIndex
from app.services.document_validation import DocumentValidationCache


def test_unchanged_files_reuse_content_validation_but_directory_changes_are_immediate(tmp_path, monkeypatch):
    cache = DocumentValidationCache()
    path = tmp_path / "CTE_8-10-1559.pdf"
    path.write_bytes(b"%PDF-valid")
    original = Path.open
    reads = []

    def opened(file_path, *args, **kwargs):
        reads.append(file_path)
        return original(file_path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    for _ in range(2):
        index = DocumentIndex(cache)
        assert index.files(tmp_path, {".pdf"}) == [path]
        assert index.valid_pdf(path)
    assert reads == [path]
    before = path.stat()
    with original(path, "wb") as stream:
        stream.write(b"<html>bad!")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
    changed = DocumentIndex(cache)
    assert changed.files(tmp_path, {".pdf"}) == [path]
    assert not changed.valid_pdf(path)
    assert reads == [path, path]
    path.unlink()
    assert DocumentIndex(cache).files(tmp_path, {".pdf"}) == []
    with original(path, "wb") as stream:
        stream.write(b"%PDF-new!!")
    added = DocumentIndex(cache)
    assert added.files(tmp_path, {".pdf"}) == [path] and added.valid_pdf(path)


def test_cached_xml_identity_is_still_checked_for_each_cte_and_reloaded_on_modification(tmp_path):
    cache = DocumentValidationCache()
    path = tmp_path / "CTE_8-10-1559.xml"
    template = '<CTe xmlns="http://www.portalfiscal.inf.br/cte"><infCte Id="CTe{key}"><ide><serie>10</serie><nCT>1559</nCT></ide></infCte></CTe>'
    path.write_text(template.format(key="2" * 44))
    row = {"filial": 8, "serie": 10, "documento": 1559, "cteId": "2" * 44}
    index = DocumentIndex(cache)
    index.files(tmp_path, {".xml"})
    index.validate_xml(path, row)
    with pytest.raises(ValueError, match="chave"):
        index.validate_xml(path, {**row, "cteId": "3" * 44})
    before = path.stat()
    path.write_text(template.format(key="3" * 44))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
    changed = DocumentIndex(cache)
    changed.files(tmp_path, {".xml"})
    with pytest.raises(ValueError, match="chave"):
        changed.validate_xml(path, row)
    changed.validate_xml(path, {**row, "cteId": "3" * 44})


def test_validation_cache_expires_and_evicts_old_entries():
    clock, reads = [0], []
    cache = DocumentValidationCache(max_entries=2, max_age=30, clock=lambda: clock[0])
    reader = lambda path: reads.append(path) or True
    cache.read(Path("a"), (1, 2, 3), "pdf", reader)
    cache.read(Path("a"), (1, 2, 3), "pdf", reader)
    assert len(reads) == 1
    clock[0] = 30
    cache.read(Path("a"), (1, 2, 3), "pdf", reader)
    assert len(reads) == 2
    cache.read(Path("b"), (1, 2, 3), "pdf", reader)
    cache.read(Path("c"), (1, 2, 3), "pdf", reader)
    cache.read(Path("a"), (1, 2, 3), "pdf", reader)
    assert len(reads) == 5
