from app.services.capture_cleanup import clean_capture_roots


def test_cleanup_preserves_downloaded_evidence(tmp_path):
    workspace = tmp_path / "workspace"
    backend = workspace / "BACKEND"
    pdf = workspace / "captures" / "rodopar-pdfs-downloads" / "CTE_2-10-10402.pdf"
    xml = workspace / "captures" / "cte-fazenda-downloads" / "CTE_2-10-10402.xml"
    zip_file = workspace / "captures" / "tarifario-zips" / "CTE_2-10-10402.zip"
    transient = workspace / "captures" / "debug" / "temp.txt"
    pointer_map = workspace / "captures" / "rodopar-pointer-map.json"
    backend_temp = backend / "captures" / "debug" / "temp.txt"

    for path in (pdf, xml, zip_file, transient, pointer_map, backend_temp):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("conteudo", encoding="utf-8")

    result = clean_capture_roots(workspace, backend)

    assert result["errors"] == []
    assert pdf.exists()
    assert xml.exists()
    assert zip_file.exists()
    assert pointer_map.exists()
    assert not transient.exists()
    assert not backend_temp.exists()
