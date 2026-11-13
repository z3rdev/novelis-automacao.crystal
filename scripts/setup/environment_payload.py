"""Compose an explicitly requested private configuration without logging values."""
import re
from pathlib import Path

ASSIGNMENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
LICENSE_FIELD = re.compile(r"^(?:PIDKEY|KEY|SN|SERIAL(?:_NUMBER)?|SETUP_CODE|REGISTRATION_NUMBER)$|CRYSTAL.*(?:LICENSE|PIDKEY|SERIAL|PRODUCT_KEY)", re.IGNORECASE)
FORCED = {"STORAGE_DIR": "../runtime", "CRYSTAL_REPORTS_PROGID": "CrystalDesignRunTime.Application.11",
          "CRYSTAL_DACTE_RPT_PATH": "", "CRYSTAL_CODE128_PROVIDER": "python"}


def assignments(raw: str) -> dict[str, str]:
    result = {}
    for line in raw.lstrip("\ufeff").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = ASSIGNMENT.fullmatch(line)
        if not match:
            raise ValueError("Configuracao deve conter atribuicoes simples em uma linha.")
        key, value = match.groups()
        if key in result:
            raise ValueError("Configuracao possui variaveis duplicadas.")
        if LICENSE_FIELD.search(key):
            raise ValueError("Chaves de licenca Crystal nao pertencem ao perfil operacional.")
        result[key] = value
    return result


def populated(value: str) -> bool:
    return bool(value.strip().strip('"').strip("'"))


def compose(defaults: str, supplied: str) -> tuple[str, list[str]]:
    profile = assignments(supplied)
    if not profile or not any(populated(value) for value in profile.values()):
        raise ValueError("Perfil operacional vazio.")
    overrides = {key: value for key, value in profile.items() if populated(value)}
    overrides.update(FORCED)
    lines, seen = [], set()
    for line in defaults.lstrip("\ufeff").splitlines():
        match = ASSIGNMENT.fullmatch(line)
        if match:
            key = match.group(1)
            seen.add(key)
            if key in overrides:
                line = key + "=" + overrides[key]
        lines.append(line)
    for key, value in overrides.items():
        if key not in seen:
            lines.append(key + "=" + value)
    text = "\n".join(lines) + "\n"
    # Validate the output, retaining original quoting and Windows/UNC paths.
    assignments(text)
    return text, sorted(overrides)


def stage(root: Path, defaults: str, source: Path | None, restrict) -> dict:
    folder = root / "runtime/installer-inputs/private-configuration"
    if source is None:
        # Disable stale private inputs without reading their contents.
        if folder.is_dir():
            for name in ("BACKEND.env", "profile.keys"):
                path = folder / name
                if path.is_file():
                    path.unlink()
        return {"included": False}
    try:
        raw = source.read_text(encoding="utf-8-sig")
    except Exception:  # noqa: BLE001 -- Never expose private configuration through a traceback.
        raise ValueError("Nao foi possivel ler o perfil operacional autorizado.") from None
    text, keys = compose(defaults, raw)
    folder.mkdir(parents=True, exist_ok=True)
    restrict(folder)  # Restrict before writing any credentials.
    (folder / "BACKEND.env").write_text(text, encoding="utf-8")
    (folder / "profile.keys").write_text("\n".join(keys) + "\n", encoding="ascii")
    restrict(folder)
    return {"included": True, "authoritative_keys": len(keys),
            "contains_operational_credentials": True, "license_keys_included": False}
