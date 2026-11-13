from pathlib import Path


def env_paths(root: Path) -> tuple[Path, Path]:
    backend = root / "BACKEND"
    return backend / ".env.example", backend / ".env"


def read_env_values(root: Path) -> dict[str, str]:
    example, active = env_paths(root)
    values: dict[str, str] = {}
    for path in (example, active):
        if not path.exists():
            continue
        values.update(parse_env(path.read_text(encoding="utf-8")))
    return values


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values


def update_env_values(root: Path, updates: dict[str, str]) -> None:
    _, active = env_paths(root)
    active.parent.mkdir(parents=True, exist_ok=True)
    lines = active.read_text(encoding="utf-8").splitlines() if active.exists() else []
    handled: set[str] = set()
    output: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            output.append(raw_line)
            continue
        key = raw_line.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={clean_value(updates[key])}")
            handled.add(key)
        else:
            output.append(raw_line)
    missing = [key for key in updates if key not in handled]
    if missing and output and output[-1].strip():
        output.append("")
    for key in missing:
        output.append(f"{key}={clean_value(updates[key])}")
    active.write_text("\n".join(output) + "\n", encoding="utf-8")


def clean_value(value: str) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").strip()

