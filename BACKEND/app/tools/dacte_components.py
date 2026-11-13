import ctypes
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path


def pe_architecture(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b"MZ":
            return "invalid"
        stream.seek(struct.unpack_from("<I", header, 60)[0])
        signature = stream.read(6)
    if len(signature) != 6 or signature[:4] != b"PE\0\0":
        return "invalid"
    return {0x14C: "x86", 0x8664: "x64", 0xAA64: "arm64"}.get(
        struct.unpack_from("<H", signature, 4)[0], "unknown"
    )


def verify_installer(path: Path, component: dict) -> None:
    if not component.get("sha256"):
        raise ValueError(
            "Instalador ainda nao catalogado. Instale a midia oficial de forma assistida e repita o diagnostico."
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != component["sha256"]:
        raise ValueError(
            "Hash diferente do pacote inspecionado. A versao/licenca precisa ser catalogada explicitamente."
        )
    if pe_architecture(path) not in {"x86", "x64"}:
        raise ValueError("O instalador nao e um executavel Windows compativel.")
    if (
        component["engine"].startswith("inno-")
        and b"Inno Setup Setup Data" not in path.read_bytes()
    ):
        raise ValueError("O pacote nao corresponde ao mecanismo Inno Setup catalogado.")


def prepare_components(
    root: Path, environment: dict, inputs: dict, assist: bool, silent: bool = False,
    qr_provider: str = "python",
    code128_provider: str | None = None,
) -> list:
    if code128_provider is None:
        code128_provider = qr_provider
    catalog = json.loads(
        (root / "installer" / "dacte" / "dependencies.json").read_text(encoding="utf-8")
    )
    manifest_path = root / "assets" / "reports" / "dacte.manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    )
    fonts = {f.casefold() for f in environment.get("fonts", [])}
    required = manifest.get("required_fonts", [])
    results = []
    for component in catalog["components"]:
        component_id = component["id"]
        if component_id == "barcodesoft":
            if qr_provider == "python":
                results.append({"component": component_id, "status": "not_required"})
                continue
            qr_fonts = [f for f in required if "bcs" in f.casefold()]
            ready = environment.get("bcs_functions", {}).get("available", False) and all(
                f.casefold() in fonts for f in qr_fonts
            )
        elif component_id == "code128":
            if code128_provider == "python":
                results.append({"component": component_id, "status": "not_required"})
                continue
            code_fonts = [f for f in required if "128" in f]
            ready = bool(code_fonts) and all(f.casefold() in fonts for f in code_fonts)
        else:
            ready = environment.get("compatible", False)
        if ready:
            results.append({"component": component_id, "status": "already_present"})
            continue
        if component_id == "crystal":
            results.append({"component": component_id, "status": "prerequisite_required",
                            "message": "Execute novamente o instalador Novelis com o pre-requisito RDC homologado."})
            continue
        bundled = root / "installer-cache" / "dacte" / str(component.get("filename") or "missing")
        explicit = inputs.get(component_id)
        path = Path(explicit) if explicit else bundled
        if not path.is_file() or (not explicit and not component.get("redistribution_approved")):
            results.append(
                {
                    "component": component_id,
                    "status": "assisted_install_required",
                    "official_url": component["official_url"],
                }
            )
            continue
        if explicit and not assist:
            results.append({"component": component_id, "status": "explicit_assisted_mode_required"})
            continue
        try:
            verify_installer(path, component)
            log = root / "runtime" / "installation" / (component_id + "-setup.log")
            log.parent.mkdir(parents=True, exist_ok=True)
            # Both supplied EXEs were positively identified as Inno Setup 6.
            arguments = ["/SP-", "/NORESTART", "/NOCLOSEAPPLICATIONS", f"/LOG={log}"]
            if silent:
                if not component.get("redistribution_approved"):
                    raise ValueError(
                        "O pacote DEMO fornecido pelo usuario exige instalacao assistida; nao ha aprovacao para uso silencioso."
                    )
                arguments += ["/VERYSILENT", "/SUPPRESSMSGBOXES"]
            result = subprocess.run([str(path), *arguments], check=False)
            results.append(
                {
                    "component": component_id,
                    "status": "installed" if result.returncode == 0 else "failed",
                    "exit_code": result.returncode,
                    "recheck_required": True,
                }
            )
        except (OSError, ValueError) as exc:
            status = "needs_admin" if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 740 else "failed"
            results.append({"component": component_id, "status": status, "message": str(exc)})
    return results


def register_barcodesoft(environment: dict) -> dict:
    component = environment.get("barcodesoft", {})
    path = Path(component.get("path") or "missing")
    if component.get("registered") and environment.get("bcs_functions", {}).get("available"):
        return {"status": "already_registered"}
    if not path.is_file():
        return {"status": "missing", "message": "Instale o componente Barcodesoft x86 oficial."}
    if pe_architecture(path) != "x86":
        return {
            "status": "wrong_architecture",
            "message": "Recusado registro de DLL que nao e x86.",
        }
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return {"status": "needs_admin"}
    program = Path(os.environ["SystemRoot"]) / "SysWOW64" / "regsvr32.exe"
    result = subprocess.run(
        [str(program), "/s", str(path)], check=False, creationflags=subprocess.CREATE_NO_WINDOW
    )
    if result.returncode == 0:
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 2, 3000, None)
    return {
        "status": "registered" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "recheck_required": True,
    }
