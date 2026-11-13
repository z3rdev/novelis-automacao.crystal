import pytest

from app.services.cte_pdf_files import find_pdf_evidence, pdf_target


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


def test_new_pdf_location_uses_existing_document_folder_convention(tmp_path):
    assert pdf_target(tmp_path, {"filial": "02", "serie": "010", "documento": "0017419"}) == (
        tmp_path / "cte-17419/CTE_2-10-17419.pdf")


@pytest.mark.parametrize("folder", ["", "cte-397", "cte_397"])
@pytest.mark.parametrize("name", ["CTE_1-10-397.pdf", "1-10-397.pdf", "cte_1_10_397.pdf"])
def test_existing_names_and_folders_are_discovered(tmp_path, folder, name):
    directory = tmp_path / folder
    directory.mkdir(exist_ok=True)
    path = directory / name
    path.write_bytes(b"%PDF-existing")
    assert find_pdf_evidence(tmp_path, {"filial": 1, "serie": 10, "documento": 397}) == path


def test_canonical_folder_is_preferred_over_old_root_file(tmp_path):
    row = {"filial": 1, "serie": 10, "documento": 397}
    target = pdf_target(tmp_path, row)
    target.parent.mkdir()
    target.write_bytes(b"%PDF-organized")
    (tmp_path / target.name).write_bytes(b"%PDF-old-root")
    assert find_pdf_evidence(tmp_path, row) == target
