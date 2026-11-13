"""Build the controlled RDC prerequisite. Never pass a PIDKEY on a command line."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from uuid import UUID, uuid5
from datetime import UTC, datetime
from pathlib import Path

from crystal.msi_database import inspect_package
from crystal.policy import distribution_approval, read_key, redact, restrict_directory, sha256, verify_modules

ROOT = Path(__file__).resolve().parents[1]


def build(args):
    lock = json.loads((ROOT / "installer/crystal/modules.lock.json").read_text(encoding="utf-8"))
    modules = verify_modules(args.modules, lock)
    if args.mode == "distribution":
        distribution_approval(args.approval)
    if args.verify_only:
        return {"status": "inputs_verified", "modules": modules, "production_ready": False}
    if args.key_file is None:
        raise ValueError("Forneca --key-file de fonte autorizada; nao passe a chave como argumento.")
    key = read_key(args.key_file, args.key_field)
    if not args.wix.is_file():
        raise ValueError("WiX ausente. Execute scripts/bootstrap-crystal-build-tools.ps1.")
    output = ROOT / "runtime/crystal-build" / args.mode
    output.mkdir(parents=True, exist_ok=True)
    # The compiled MSI contains the configured license property. Restrict local artifacts.
    restrict_directory(output)
    package = output / f"NovelisCrystalRDC-x86-{args.package_version}.msi"
    manifest = package.with_suffix(".manifest.json")
    # Invalidate an earlier success before any compilation attempt.
    manifest.unlink(missing_ok=True)
    (output / "build.log").unlink(missing_ok=True)
    environment = dict(os.environ, NOVELIS_CRYSTAL_PIDKEY=key,
                       NOVELIS_CRYSTAL_MODULES=str(args.modules.resolve()),
                       NOVELIS_CRYSTAL_BUILD_MODE=args.mode,
                       NOVELIS_CRYSTAL_PACKAGE_VERSION=args.package_version,
                       NOVELIS_CRYSTAL_PRODUCT_CODE=str(uuid5(
                           UUID("ed22cf99-8620-4c90-b465-941460894f26"), args.package_version)).upper())
    try:
        with tempfile.TemporaryDirectory(prefix="wix-", dir=output) as intermediate:
            result = subprocess.run(
                ["dotnet", str(args.wix), "build", "-arch", "x86", "-pdbtype", "none",
                 "-intermediatefolder", intermediate, "-out", str(package),
                 str(ROOT / "installer/crystal/Product.wxs")],
                env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
            )
            # The compiler may echo expanded source on failure; redact before saving or printing.
            log = redact(result.stdout + result.stderr, key)
            (output / "build.log").write_text(log, encoding="utf-8")
            if result.returncode:
                raise ValueError("WiX falhou; consulte o log sanitizado do build.")
        audit = inspect_package(package, key)
        data = {"schema_version": 1, "filename": package.name, "sha256": sha256(package),
                "built_at": datetime.now(UTC).isoformat(), "build_mode": args.mode,
                "runtime_version": lock["runtime_version"], "architecture": "x86",
                "structure_verified": True, "production_ready": False,
                "redistribution_approved": args.mode == "distribution", "modules": modules, "audit": audit}
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return {"status": "built", "manifest": str(manifest), "production_ready": False,
                "redistribution_approved": data["redistribution_approved"]}
    finally:
        environment.pop("NOVELIS_CRYSTAL_PIDKEY", None)
        key = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["development", "distribution"], default="development")
    parser.add_argument("--modules", type=Path, default=Path(r"C:\Program Files (x86)\Common Files\Merge Modules"))
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--key-field", default="KEY", help="Empty string means a file containing only the key")
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--package-version", default="1.0.1", choices=["1.0.1", "1.0.2"],
                        help="1.0.1 fixes standard action sequencing; 1.0.2 is reserved for upgrade tests")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--wix", type=Path, default=ROOT / "runtime/tools/wix-4.0.6/tools/net6.0/any/wix.dll")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args)))
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        # Exceptions may contain expanded compiler/configuration text. No traceback with secrets.
        message = str(exc) if type(exc) in {ValueError, RuntimeError} else "Falha de entrada/ferramenta; valor de PIDKEY omitido."
        print(json.dumps({"status": "blocked", "message": message,
                          "production_ready": False}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
