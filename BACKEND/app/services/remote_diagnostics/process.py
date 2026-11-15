"""Run a bounded local probe and terminate only its own subprocess tree."""

import asyncio
import json
import os
import subprocess
import sys

import psutil

FRAME = b"DIAGNOSTIC_RESULT="
MAX_FRAME = 2_000_000


def stop_tree(pid, created):
    try:
        root = psutil.Process(pid)
        if root.create_time() != created:
            return
        children = root.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        root.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


class ProbeRunner:
    def __init__(self, settings, timeout=180):
        self.settings, self.timeout = settings, timeout

    async def collect(self, options):
        python = self.settings.backend_root / ".venv/Scripts/python.exe"
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONHOME", "PYTHONPATH"}
        }
        env["PYTHONNOUSERSITE"] = "1"
        env["STORAGE_DIR"] = str(self.settings.storage_dir)
        env["NOVELIS_SQLITE_PATH"] = str(self.settings.novelis_sqlite_path or "")
        process = await asyncio.create_subprocess_exec(
            str(python) if python.is_file() else sys.executable,
            "-I",
            "-m",
            "app.services.remote_diagnostics.probe",
            "--max-runs",
            str(options.max_runs),
            "--days-back",
            str(options.days_back),
            cwd=self.settings.backend_root,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=MAX_FRAME,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            created = psutil.Process(process.pid).create_time()
        except psutil.NoSuchProcess:
            created = None
        latest = None

        async def receive():
            nonlocal latest
            while line := await process.stdout.readline():
                if line.startswith(FRAME):
                    value = json.loads(line[len(FRAME) :])
                    if not isinstance(value, dict) or value.get("schema_version") != 1:
                        raise ValueError("invalid_probe_result")
                    latest = value
            await process.wait()

        reason = ""
        try:
            await asyncio.wait_for(receive(), self.timeout)
            if process.returncode:
                reason = "probe_failed"
        except TimeoutError:
            reason = "probe_timeout"
        except (ValueError, OSError):
            reason = "invalid_probe_result"
        finally:
            if process.returncode is None:
                if created is not None:
                    await asyncio.to_thread(stop_tree, process.pid, created)
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                await asyncio.wait_for(process.wait(), 5)
        if latest is None:
            raise RuntimeError(reason or "probe_failed")
        if reason:
            latest["complete"] = False
            latest["incomplete_reason"] = reason
        return latest
