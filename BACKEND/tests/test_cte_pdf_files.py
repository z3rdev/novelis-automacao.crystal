from app.services.cte_pdf_files import find_pdf_evidence


def test_pdf_identity_includes_filial_serie_and_number(tmp_path):
    row = {"filial": 1, "serie": 10, "documento": 397}
    other = tmp_path / "cte-397"
    other.mkdir()
    (other / "CTE_11-10-397.pdf").write_bytes(b"%PDF-another-branch")
    (tmp_path / "CTE_1-10-1397.pdf").write_bytes(b"%PDF-another-number")
    exact = tmp_path / "CTE_1-10-397.pdf"
    exact.write_text("<html>erro</html>")
    assert find_pdf_evidence(tmp_path, row) is None
    exact.write_bytes(b"%PDF-valid")
    assert find_pdf_evidence(tmp_path, row) == exact
