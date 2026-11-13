from dataclasses import dataclass
from pathlib import Path

from app.config.settings import Settings


SECRET_MARKERS = ("PASS", "PASSWORD", "SENHA", "TOKEN", "SECRET", "ASSINATURA")


@dataclass(frozen=True)
class EnvEntry:
    key: str
    value: str
    source: str
    group: str
    is_secret: bool

    def to_public(self) -> dict[str, object]:
        value = "********" if self.is_secret and self.value else self.value
        return {
            "key": self.key,
            "value": value,
            "source": self.source,
            "group": self.group,
            "isSecret": self.is_secret,
            "hasValue": bool(self.value),
        }


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values


def env_group(key: str) -> str:
    if key.startswith("PRE_"):
        return "PRE-PASSO"
    if key.startswith("NOVELIS_"):
        return "NOVELIS"
    if key.startswith("GNRE_"):
        return "GNRE"
    if key.startswith("MONITOR_"):
        return "MONITOR"
    if key.startswith("CONSULTA_DB_"):
        return "CONSULTA DB"
    if key.startswith("CONSULTA_"):
        return "CONSULTA"
    if key.startswith("MULTI_AGENT_"):
        return "MULTI-AGENTE"
    if key.startswith("BROWSER_") or key.startswith("WINDOW_") or key.startswith("SESSION_"):
        return "NAVEGADOR"
    if key.startswith("AUTO_") or key.startswith("AUTOMATION_"):
        return "EXECUCAO"
    if key.startswith("SYSTEM_") or key.startswith("REPROCESS_") or key.startswith("SERVICE_"):
        return "SISTEMA"
    if key.startswith("OBSERVACAO_"):
        return "REGRAS"
    if key.startswith("APP_") or key.startswith("API_") or key.startswith("FRONTEND_"):
        return "API"
    return "GERAL"


def is_secret_key(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in SECRET_MARKERS)


class EnvCatalog:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def entries(self) -> list[EnvEntry]:
        example_values = read_env_file(self.settings.backend_root / ".env.example")
        active_values = read_env_file(self.settings.backend_root / ".env")
        keys = sorted(set(example_values) | set(active_values))

        entries: list[EnvEntry] = []
        for key in keys:
            source = "active" if key in active_values else "example"
            value = active_values.get(key, example_values.get(key, ""))
            entries.append(
                EnvEntry(
                    key=key,
                    value=value,
                    source=source,
                    group=env_group(key),
                    is_secret=is_secret_key(key),
                )
            )
        return entries

    def grouped_public(self) -> dict[str, object]:
        groups: dict[str, list[dict[str, object]]] = {}
        for entry in self.entries():
            groups.setdefault(entry.group, []).append(entry.to_public())
        return {
            "total": sum(len(items) for items in groups.values()),
            "groups": groups,
        }
