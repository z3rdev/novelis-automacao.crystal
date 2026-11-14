import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("installer_receipt", ROOT / "scripts/setup/installer_receipt.py")
receipt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receipt)


def test_packaged_source_receipt_excludes_credentials_and_python_cache(tmp_path):
    (tmp_path / "services").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "services/developer_monitor.py").write_text("# packaged source\n")
    (tmp_path / "__pycache__/module.pyc").write_bytes(b"fixture")
    for name in [".env", ".env.local", "error.log", "module.pyc", "module.pyo"]:
        (tmp_path / name).write_text("synthetic private value")
    result = receipt.packaged_sources(tmp_path)
    assert list(result) == ["services/developer_monitor.py"]
    assert len(result["services/developer_monitor.py"]) == 64


def test_installer_extracts_the_same_validated_msi_selected_during_build():
    main = (ROOT / "installer/AutomacaoNovelis.iss").read_text()
    prerequisite = (ROOT / "installer/crystal/Prerequisite.iss").read_text()
    build = (ROOT / "scripts/build-installer.ps1").read_text()
    assert 'crystal\\{#CrystalRuntimeFilename}' in main
    assert "ExtractTemporaryFile('{#CrystalRuntimeFilename}')" in prerequisite
    assert '"/DCrystalRuntimeFilename=$CrystalRuntimeFilename"' in build


def test_official_desktop_build_starts_with_local_backend_and_current_icon():
    build = (ROOT / "scripts/build-hub-desktop.ps1").read_text()
    inno = (ROOT / "installer/AutomacaoNovelis.iss").read_text()
    assert "$env:VITE_DEFAULT_API_MODE = 'local'" in build
    assert "$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000/api/hub'" in build
    assert 'SetupIconFile=..\\FRONTEND-HUB\\src-tauri\\icons\\icon.ico' in inno
    assert 'DestName: "icon.desktop.ico"' in inno
    assert '..\\FRONTEND\\src\\assets\\icon.desktop.ico' not in inno
