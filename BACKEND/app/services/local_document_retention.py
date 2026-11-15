"""Weekly retention applies only to generated local PDF/XML, never UNC archives."""
import asyncio
import logging
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
CAPTURE_DIRS = ("rodopar-pdfs-downloads", "cte-fazenda-downloads", "tarifario-downloads", "novelis-chamados-direto")


def clean_local_documents(workspace: Path, storage: Path, *, now=None, dry_run=False):
    now = now or datetime.now().astimezone()
    cutoff = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    roots = [storage / "reports/dacte"]
    roots.extend(base / directory for base in (workspace / "captures", workspace / "BACKEND/captures") for directory in CAPTURE_DIRS)
    result = {"deleted": 0, "eligible": 0, "errors": 0, "skipped_roots": 0, "dry_run": dry_run,
              "week_started_at": datetime.fromtimestamp(cutoff, now.tzinfo).isoformat()}
    for root in roots:
        if str(root).startswith(("\\\\", "//")) or not root.is_dir():
            result["skipped_roots"] += 1
            continue
        resolved_root = root.resolve()
        if str(resolved_root).startswith(("\\\\", "//")) or _remote_drive(resolved_root) or _linked(root):
            result["skipped_roots"] += 1
            continue
        for directory, names, files in os.walk(root, followlinks=False):
            # Junctions and linked directories may point at shared or unrelated data.
            names[:] = [name for name in names if not _linked(Path(directory) / name)]
            for name in files:
                path = Path(directory) / name
                try:
                    if path.suffix.lower() not in {".pdf", ".xml"} or _linked(path):
                        continue
                    if not path.resolve().is_relative_to(resolved_root) or path.stat().st_mtime >= cutoff:
                        continue
                    result["eligible"] += 1
                    if not dry_run:
                        path.unlink()
                        result["deleted"] += 1
                except OSError:
                    result["errors"] += 1
    return result


def _linked(path):
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024))
    except OSError:
        return True


def _remote_drive(path):
    if os.name != "nt":
        return False
    import ctypes
    # DRIVE_REMOTE also catches shares mounted on a drive letter.
    return ctypes.windll.kernel32.GetDriveTypeW(str(path.anchor)) == 4


class LocalDocumentRetention:
    def __init__(self, settings, config, automation):
        self.settings, self.config, self.automation = settings, config, automation
        self.task = None

    async def tick(self):
        if str(self.config.get("LOCAL_DOCUMENT_RETENTION_ENABLED") or "true").lower() not in {"true", "1", "yes", "sim"}:
            return
        # Prevent starting a run while deleting its local temporary documents.
        async with self.automation._control_lock:
            if (await self.automation.current()).status in {"running", "stopping"}:
                return
            result = await asyncio.to_thread(clean_local_documents, self.settings.backend_root.parent, self.settings.storage_dir)
            if result["deleted"] or result["errors"]:
                logger.info("Retenção semanal local: %s PDF/XML removido(s), %s erro(s).", result["deleted"], result["errors"])

    async def loop(self):
        while True:
            try:
                await self.tick()
            except OSError:
                logger.warning("Limpeza semanal local aguardando disponibilidade dos arquivos.")
            await asyncio.sleep(3600)

    def start(self):
        self.task = asyncio.create_task(self.loop())

    async def close(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
