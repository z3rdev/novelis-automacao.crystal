import os
from pathlib import Path
import sys


def find_project_root(start: Path) -> Path:
    env_root = os.environ.get("AUTOMACAO_NOVELIS_ROOT")
    if env_root:
        return Path(env_root).resolve()
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)
    candidates.extend([start.resolve(), *start.resolve().parents])
    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])
    for candidate in candidates:
        if (candidate / "BACKEND").exists() and ((candidate / "FRONTEND").exists() or (candidate / "FRONTEND-HUB").exists()):
            return candidate
    return cwd
