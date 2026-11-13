import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from crystal.policy import distribution_approval, read_key, redact, restrict_directory, sha256, verify_modules, verify_payload
from crystal.sequence import verify_execute_sequence


@pytest.mark.parametrize("delimiter", ["=", ":", "-", " "])
def test_only_authorized_key_field_is_selected(tmp_path, delimiter):
    # Synthetic format fixture, unrelated to a real product license.
    value = "AAAAA-BBBBBBB-CCCCCCC-DDDD"
    path = tmp_path / "private.txt"
    path.write_text(f"Setup Code: other\nSN: 1234567890\nKEY {delimiter} {value}\nRegistro: 0987654321")
    assert read_key(path) == value


@pytest.mark.parametrize("text", ["KEY=invalid", "SN=1234567890", "KEY=a\nKEY=b"])
def test_invalid_or_ambiguous_key_never_appears_in_errors(tmp_path, text):
    path = tmp_path / "private.txt"
    path.write_text(text)
    with pytest.raises(ValueError) as error:
        read_key(path)
    assert text not in str(error.value)


def test_compiler_log_redacts_case_changes_and_key_without_separators():
    value = "AAAAA-BBBBBBB-CCCCCCC-DDDD"
    assert redact(value.lower() + " " + value.replace("-", ""), value) == "<redacted> <redacted>"


@pytest.mark.skipif(os.name != "nt", reason="NTFS permission regression")
def test_restricting_existing_artifacts_twice_preserves_file_access(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir()
    child = directory / "intermediate"
    child.mkdir()
    artifact = child / "fixture.txt"
    artifact.write_text("synthetic artifact")
    restrict_directory(directory)
    restrict_directory(directory)
    artifact.write_text(artifact.read_text() + " rebuilt")
    assert artifact.read_text() == "synthetic artifact rebuilt"


def test_changed_merge_module_is_blocked(tmp_path):
    path = tmp_path / "sample.msm"
    path.write_bytes(b"trusted inventory fixture")
    lock = {"runtime_version": "11.5.0.313", "modules": [{"filename": path.name, "sha256": sha256(path)}] * 4}
    assert len(verify_modules(tmp_path, lock)) == 4
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="inventario"):
        verify_modules(tmp_path, lock)


def approval_file(tmp_path):
    evidence = tmp_path / "entitlement.txt"
    evidence.write_text("Synthetic approval fixture")
    data = {"schema_version": 1, "runtime_version": "11.5.0.313", "approved_by": "reviewer",
            "approved_at": "2026-11-12", "deployment_scope": "internal", "package_sha256": "expected"}
    for section in ("provenance", "license"):
        data[section] = {"approved": True, "evidence_file": evidence.name, "sha256": sha256(evidence)}
    path = tmp_path / "approval.json"
    path.write_text(json.dumps(data))
    return path


def test_distribution_without_approval_is_blocked():
    with pytest.raises(ValueError, match="bloqueada"):
        distribution_approval(None)


def test_approval_requires_unchanged_evidence_and_specific_package(tmp_path):
    path = approval_file(tmp_path)
    assert distribution_approval(path, "expected")["deployment_scope"] == "internal"
    with pytest.raises(ValueError, match="MSI"):
        distribution_approval(path, "other")
    (tmp_path / "entitlement.txt").write_text("changed")
    with pytest.raises(ValueError, match="adulterada"):
        distribution_approval(path)


def test_development_artifact_cannot_be_staged_for_distribution(tmp_path):
    package = tmp_path / "runtime.msi"
    package.write_bytes(b"Synthetic MSI fixture")
    path = tmp_path / "manifest.json"
    data = {"filename": package.name, "sha256": sha256(package), "runtime_version": "11.5.0.313",
            "architecture": "x86", "structure_verified": True, "build_mode": "development",
            "audit": {"execute_sequence_verified": True}}
    path.write_text(json.dumps(data))
    assert verify_payload(path, "development")[1] == package
    with pytest.raises(ValueError, match="desenvolvimento"):
        verify_payload(path, "distribution", approval_file(tmp_path))
    package.write_bytes(b"changed")
    with pytest.raises(ValueError, match="integridade"):
        verify_payload(path, "development")


def test_existing_full_crystal_or_foreign_machine_is_not_clean_vm_evidence():
    spec = importlib.util.spec_from_file_location("crystal_vm_test", SCRIPTS / "test-crystal-dacte.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    baseline = {"machine_uuid": "vm-a", "checked_at": "2026-11-12T10:00",
                "schema_version": 1, "process_bits": 32, "any_crystal_registered": False,
                "full_editor_installed": False, "installed_crystal_products": [],
                "dlls": [{"exists": False}] * 5}
    current = {"machine_uuid": "vm-a", "full_editor_installed": False}
    installation = {"status": "installed_verified", "package_sha256": "hash", "checked_at": "2026-11-12T11:00"}
    manifest = {"sha256": "hash"}
    assert module.clean_baseline_matches(baseline, current, installation, manifest)
    baseline["full_editor_installed"] = True
    assert not module.clean_baseline_matches(baseline, current, installation, manifest)
    baseline["full_editor_installed"] = False
    current["machine_uuid"] = "foreign-machine"
    assert not module.clean_baseline_matches(baseline, current, installation, manifest)


def valid_sequence():
    order = {"InstallInitialize": 1500, "UnpublishComponents": 1700, "SelfUnregModules": 2200,
             "RemoveRegistryValues": 2600, "RemoveFiles": 3500, "RemoveFolders": 3600,
             "CreateFolders": 3700, "InstallFiles": 4000, "WriteRegistryValues": 5000,
             "SelfRegModules": 5600, "PublishComponents": 6200, "InstallFinalize": 6600}
    return [[name, "", str(number)] for name, number in order.items()]


def test_registration_action_is_scheduled_after_file_installation():
    result = verify_execute_sequence(valid_sequence())
    assert result["InstallFiles"] < result["SelfRegModules"] < result["InstallFinalize"]


def test_missing_selfreg_action_is_rejected_even_when_file_table_exists():
    rows = [row for row in valid_sequence() if row[0] != "SelfRegModules"]
    with pytest.raises(ValueError, match="SelfRegModules"):
        verify_execute_sequence(rows)


@pytest.mark.parametrize("condition,number", [("0", "5600"), ("", "0"), ("FALSE", "5600")])
def test_disabled_or_unscheduled_registration_is_rejected(condition, number):
    rows = valid_sequence()
    for row in rows:
        if row[0] == "SelfRegModules":
            row[1:] = [condition, number]
    with pytest.raises(ValueError, match="SelfRegModules"):
        verify_execute_sequence(rows)


def test_registering_before_installfiles_is_rejected():
    rows = valid_sequence()
    for row in rows:
        if row[0] == "SelfRegModules":
            row[2] = "3900"
    with pytest.raises(ValueError, match="Ordem"):
        verify_execute_sequence(rows)
