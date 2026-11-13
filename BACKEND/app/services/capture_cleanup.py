from pathlib import Path


PRESERVED_EVIDENCE_DIRS = {
    "cte-fazenda-downloads",
    "gnre",
    "novelis-chamados-direto",
    "rodopar-pdfs-downloads",
    "tarifario-downloads",
    "tarifario-zips",
}

PRESERVED_EVIDENCE_EXTENSIONS = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
    ".xml",
    ".zip",
}


class CaptureCleanup:
    def __init__(self, workspace_root: Path, backend_root: Path) -> None:
        self.roots = [workspace_root / "captures", backend_root / "captures"]

    def clean(self) -> dict[str, object]:
        deleted: list[str] = []
        skipped: list[str] = []
        errors: list[dict[str, str]] = []
        for root in self.roots:
            root.mkdir(parents=True, exist_ok=True)
            self._clean_dir(root, root, deleted, skipped, errors)
        return {
            "deleted": len(deleted),
            "skipped": len(skipped),
            "errors": errors,
            "roots": [str(root) for root in self.roots],
        }

    def _clean_dir(
        self,
        root: Path,
        current: Path,
        deleted: list[str],
        skipped: list[str],
        errors: list[dict[str, str]],
    ) -> None:
        for child in list(current.iterdir()):
            try:
                resolved = child.resolve()
                if not self._inside(resolved, root.resolve()):
                    skipped.append(str(child))
                    continue
                if child.is_dir():
                    self._clean_dir(root, child, deleted, skipped, errors)
                    self._remove_empty_dir(child, deleted, errors)
                    continue
                if self._should_preserve(child):
                    skipped.append(str(child))
                    continue
                child.unlink()
                deleted.append(str(child))
            except Exception as exc:
                errors.append({"path": str(child), "error": str(exc)})

    @staticmethod
    def _inside(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _should_preserve(path: Path) -> bool:
        name = path.name.lower()
        parent = path.parent.name.lower()
        if name in {".gitkeep", ".keep"} or "pointer-map" in name:
            return True
        if parent == "novelis-relatorio-cte-xml" and name in {"relatorio_cte.json", "relatorio_cte.xlsx"}:
            return True
        if path.suffix.lower() in PRESERVED_EVIDENCE_EXTENSIONS:
            return True
        if any(part.lower() in PRESERVED_EVIDENCE_DIRS for part in path.parts):
            return True
        return False

    @staticmethod
    def _remove_empty_dir(path: Path, deleted: list[str], errors: list[dict[str, str]]) -> None:
        try:
            path.rmdir()
            deleted.append(str(path))
        except OSError:
            return
        except Exception as exc:
            errors.append({"path": str(path), "error": str(exc)})


def clean_capture_roots(workspace_root: Path, backend_root: Path) -> dict[str, object]:
    return CaptureCleanup(workspace_root, backend_root).clean()
