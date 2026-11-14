import asyncio
import os
import signal

import psutil


async def watch_desktop(pid: int, created_at: float) -> None:
    while True:
        await asyncio.sleep(2)
        try:
            parent = psutil.Process(pid)
            alive = abs(parent.create_time() - created_at) < 0.01 and parent.is_running()
        except psutil.NoSuchProcess:
            alive = False
        except psutil.AccessDenied:
            continue
        if not alive:
            # Uvicorn handles this Python signal and executes the application's shutdown hooks.
            signal.raise_signal(signal.SIGTERM)
            return


def monitor_desktop() -> asyncio.Task | None:
    try:
        pid = int(os.environ.get("NOVELIS_DESKTOP_PARENT_PID", ""))
        created_at = float(os.environ.get("NOVELIS_DESKTOP_PARENT_CREATED_AT", ""))
    except ValueError:
        return None
    return asyncio.create_task(watch_desktop(pid, created_at))
