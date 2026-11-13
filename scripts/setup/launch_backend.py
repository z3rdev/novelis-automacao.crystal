"""Start the installed local API once, without rerunning pip or Python installers."""
import json
import msvcrt
import sys
import time
from pathlib import Path
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_backend import ReadinessError, health, hub_ready, start_backend, stop_backend, valid_health, wait_ready


def launch(root: Path, port: int = 8000):
    if not (root / ".automacao-novelis-install").is_file():
        raise ReadinessError("installation_marker_missing")
    prepared = json.loads((root / "runtime/bootstrap-result.json").read_text(encoding="utf-8-sig"))
    if prepared.get("status") != "succeeded":
        raise ReadinessError("backend_preparation_incomplete")
    lock = (root / "runtime/backend-launch.lock").open("a+b")
    try:
        deadline = time.monotonic() + 100
        while True:
            try:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Backend initialization lock timed out")
                time.sleep(0.3)
        try:
            existing = health(port)
        except (URLError, OSError, TimeoutError):
            existing = None
        if existing is not None:
            if not valid_health(existing, root) or not hub_ready(port):
                raise ReadinessError("port_occupied_by_different_or_unavailable_backend")
            return
        with (root / "runtime/backend-local.log").open("a", encoding="utf-8") as log:
            process = start_backend(root, port, log)
        try:
            wait_ready(root, port, process)
            return process
        except Exception:
            stop_backend(process)
            raise
    finally:
        lock.close()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    try:
        launch(root)
    except Exception as exc:
        (root / "runtime/backend-launch-error.json").write_text(
            json.dumps({"status": "failed", "error_type": type(exc).__name__,
                        "reason": getattr(exc, "reason", "launch_error"),
                        "checks": getattr(exc, "checks", {})}), encoding="utf-8")
        sys.exit(1)
