import asyncio
import re
import shutil
import time
from pathlib import Path
from typing import Any

from playwright.async_api import Download, Page

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.config.settings import Settings


class RodoparPdfDownloadWatcher:
    def __init__(
        self,
        settings: Settings,
        config: dict[str, Any],
        row: dict[str, Any],
        emit: Emit,
        run_id: str,
    ) -> None:
        self.settings = settings
        self.config = config
        self.row = row
        self.emit = emit
        self.run_id = run_id
        self.tasks: list[asyncio.Task[str]] = []
        self.page: Page | None = None

    def attach(self, page: Page) -> None:
        self.page = page
        page.on("download", self._on_download)

    def detach(self) -> None:
        if self.page:
            try:
                self.page.remove_listener("download", self._on_download)
            except Exception:
                pass
        self.page = None

    def known_files(self) -> set[str]:
        return {
            self._path_key(file_path)
            for directory in self._download_dirs()
            for file_path in self._iter_files(directory)
        }

    async def wait_and_rename(self, known_files: set[str], started_at: float) -> str:
        wait_ms = self._positive_int(self.config.get("downloadWaitMs"), 60_000)
        deadline = time.time() + (wait_ms / 1000)
        while time.time() <= deadline:
            saved = await self._completed_download()
            if saved:
                await self._emit_saved(saved, "Download do navegador salvo")
                return saved
            candidate = await self._latest_pdf_candidate(known_files, started_at)
            if candidate:
                target = self._move_pdf_to_cte_name(candidate)
                await self._emit_saved(str(target), "PDF renomeado")
                return str(target)
            await asyncio.sleep(0.5)

        await emit_warn(
            self.emit,
            self.run_id,
            "rodopar_pdf.pdf_not_found",
            "Não localizei PDF novo para renomear depois do download Rodopar.",
            {"row": self.row, "downloadDirs": [str(path) for path in self._download_dirs()]},
        )
        return ""

    def _on_download(self, download: Download) -> None:
        self.tasks.append(asyncio.create_task(self._save_playwright_download(download)))

    async def _save_playwright_download(self, download: Download) -> str:
        target = self._target_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        await download.save_as(str(target))
        return str(target) if target.exists() and target.stat().st_size > 0 else ""

    async def _completed_download(self) -> str:
        for task in list(self.tasks):
            if not task.done():
                continue
            self.tasks.remove(task)
            try:
                result = task.result()
            except Exception as exc:
                await emit_warn(
                    self.emit,
                    self.run_id,
                    "rodopar_pdf.download_event_failed",
                    f"Falha ao salvar download do navegador: {exc}",
                    {"row": self.row},
                )
                continue
            if result:
                return result
        return ""

    async def _latest_pdf_candidate(self, known_files: set[str], started_at: float) -> Path | None:
        candidates: list[tuple[float, Path]] = []
        cutoff = started_at - 5
        for directory in self._download_dirs():
            for file_path in self._iter_files(directory):
                stat = self._stat(file_path)
                if stat is None or stat.st_size <= 0:
                    continue
                if self._path_key(file_path) in known_files and stat.st_mtime < cutoff:
                    continue
                if file_path.suffix.lower() in {".crdownload", ".tmp", ".part"}:
                    continue
                if not self._is_likely_pdf(file_path):
                    continue
                if not await self._is_stable(file_path):
                    continue
                candidates.append((stat.st_mtime, file_path))
        return max(candidates, key=lambda item: item[0])[1] if candidates else None

    def _move_pdf_to_cte_name(self, source: Path) -> Path:
        target = self._target_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        if self._path_key(source) == self._path_key(target):
            return target
        if target.exists():
            target.unlink()
        try:
            source.replace(target)
        except OSError:
            shutil.copy2(source, target)
            source.unlink(missing_ok=True)
        return target

    async def _emit_saved(self, path: str, prefix: str) -> None:
        await emit_step(
            self.emit,
            self.run_id,
            "rodopar_pdf.renamed",
            f"{prefix} em {Path(path).name}.",
            {"row": self.row, "pdfFile": path},
        )

    def _target_path(self) -> Path:
        target_root = self._resolve(str(self.config.get("downloadTargetDir") or "captures/rodopar-pdfs-downloads"))
        target_dir = target_root / f"cte-{self._safe_slug(self.row['documento'])}"
        return target_dir / f"CTE_{self._safe_name(self._cte_code())}.pdf"

    def _download_dirs(self) -> list[Path]:
        target_root = self._resolve(str(self.config.get("downloadTargetDir") or "captures/rodopar-pdfs-downloads"))
        raw_dirs = [
            self.config.get("downloadSourceDir"),
            self.settings.browser_downloads_dir,
            target_root,
            target_root / f"cte-{self._safe_slug(self.row['documento'])}",
            Path.home() / "Downloads",
            self.settings.legacy_project_dir / "captures" / "downloads",
            self.settings.legacy_project_dir / "captures" / "rodopar-pdfs-downloads",
            *self._extra_download_dirs(),
        ]
        return self._unique_dirs(raw_dirs)

    def _extra_download_dirs(self) -> list[str]:
        raw = str(self.config.get("extraDownloadDirs") or "")
        return [item.strip() for item in re.split(r"[;\n]+", raw) if item.strip()]

    def _unique_dirs(self, raw_dirs: list[Any]) -> list[Path]:
        paths: list[Path] = []
        seen: set[str] = set()
        for value in raw_dirs:
            if not value:
                continue
            path = self._resolve(str(value))
            key = self._path_key(path)
            if key not in seen:
                paths.append(path)
                seen.add(key)
        return paths

    def _iter_files(self, directory: Path) -> list[Path]:
        if not directory.exists():
            return []
        try:
            return [item for item in directory.iterdir() if item.is_file()]
        except OSError:
            return []

    async def _is_stable(self, file_path: Path) -> bool:
        first = self._stat(file_path)
        if first is None:
            return False
        await asyncio.sleep(0.35)
        second = self._stat(file_path)
        return second is not None and first.st_size == second.st_size and second.st_size > 0

    def _is_likely_pdf(self, file_path: Path) -> bool:
        if file_path.suffix.lower() == ".pdf":
            return True
        try:
            with file_path.open("rb") as file:
                return file.read(4) == b"%PDF"
        except OSError:
            return False

    def _stat(self, file_path: Path):
        try:
            return file_path.stat()
        except OSError:
            return None

    def _cte_code(self) -> str:
        return f"{self.row['filial']}-{self.row['serie']}-{self.row['documento']}"

    def _safe_name(self, value: Any) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "cte")).strip("_")

    def _safe_slug(self, value: Any) -> str:
        safe = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "item").strip().lower())
        return safe.strip("-") or "item"

    def _path_key(self, path: Path) -> str:
        return str(path.resolve(strict=False)).lower()

    def _resolve(self, value: str) -> Path:
        path = Path(str(value))
        return path if path.is_absolute() else self.settings.backend_root.parent / path

    def _positive_int(self, value: Any, fallback: int) -> int:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed > 0 else fallback
