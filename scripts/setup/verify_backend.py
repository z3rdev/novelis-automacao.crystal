"""Validate the real installed API in a child process; never run automation jobs."""
import argparse
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener


class ReadinessError(RuntimeError):
    def __init__(self, reason: str, checks: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.checks = checks or {}


def local_json(port: int, endpoint: str, timeout: int) -> dict:
    # This helper talks exclusively to loopback, independently of Windows proxies.
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}{endpoint}", timeout=timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError("invalid_local_response")
    return result


def health(port: int) -> dict:
    return local_json(port, "/api/health", 2)


def valid_health(data: dict, root: Path) -> bool:
    content = (root / "DESKTOP/automacao_novelis_desktop/config.py").read_text(encoding="utf-8")
    version = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', content).group(1)
    return (data.get("status") == "ok" and data.get("service") == "automacao-novelis-backend"
            and data.get("playwrightDriverOk") is True
            and Path(data.get("backendRoot", "")).resolve() == (root / "BACKEND").resolve()
            and data.get("version") == version)


def hub_ready(port: int) -> bool:
    return bool(local_json(port, "/api/hub/health/ping", 3).get("versao"))


def start_backend(root: Path, port: int, log):
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONHOME", "PYTHONPATH"}}
    env["PYTHONNOUSERSITE"] = "1"
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(root / "ms-playwright")
    return subprocess.Popen([str(root / "BACKEND/.venv/Scripts/python.exe"), "-I", "-m",
        "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
        "--workers", "1", "--no-access-log"], cwd=root / "BACKEND", env=env,
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def stop_backend(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        # The Windows venv redirector can have a separate interpreter child.
        subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def wait_ready(root: Path, port: int, process, timeout: int = 90) -> dict:
    deadline = time.monotonic() + timeout
    checks = {"api_responded": False}
    while time.monotonic() < deadline:
        if process.poll() is not None:
            checks["server_exit_code"] = process.returncode
            raise ReadinessError("backend_exited", checks)
        try:
            data = health(port)
            checks.update(api_responded=True, api_http_status=200)
            checks.pop("transport_error_type", None)
            if not valid_health(data, root):
                raise ReadinessError("backend_identity_or_driver_mismatch", checks)
        except HTTPError as exc:
            checks["api_http_status"] = exc.code
            time.sleep(0.3)
            continue
        except (URLError, TimeoutError, OSError) as exc:
            checks["transport_error_type"] = type(exc).__name__
            time.sleep(0.3)
            continue
        except ValueError:
            raise ReadinessError("invalid_api_response", checks) from None
        try:
            if hub_ready(port):
                return data
            raise ReadinessError("invalid_hub_response", checks)
        except HTTPError as exc:
            checks["hub_http_status"] = exc.code
            reason = "operational_database_unconfigured" if exc.code == 503 else "hub_http_error"
            raise ReadinessError(reason, checks) from None
        except ValueError:
            raise ReadinessError("invalid_hub_response", checks) from None
        except (URLError, TimeoutError, OSError) as exc:
            checks["transport_error_type"] = type(exc).__name__
            time.sleep(0.3)
    raise ReadinessError("backend_health_timeout", checks)


def verify(root: Path) -> dict:
    runtime = root / "runtime"
    runtime.mkdir(exist_ok=True)
    result = {"schema_version": 2, "status": "failed", "hub_api": False, "production_ready": False}
    process = None
    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        result["port"] = port
        with (runtime / "backend-setup.log").open("w", encoding="utf-8") as log:
            process = start_backend(root, port, log)
            data = wait_ready(root, port, process)
        result.update(status="succeeded", hub_api=True, version=data["version"],
                      identity=os.environ.get("USERNAME", ""), port=port)
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        result["reason"] = getattr(exc, "reason", "verification_error")
        result["checks"] = getattr(exc, "checks", {})
        raise RuntimeError("Verificacao do backend falhou: " + result["reason"] +
                           ". Consulte runtime/backend-readiness.json e backend-setup.log") from None
    finally:
        if process is not None:
            stop_backend(process)
        (runtime / "backend-readiness.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    print(json.dumps(verify(parser.parse_args().root.resolve())))
