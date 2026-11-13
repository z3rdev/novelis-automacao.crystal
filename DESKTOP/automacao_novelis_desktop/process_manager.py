import json
import os
import socket
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def open_frontend(frontend_url: str, view: str = "") -> None:
    url = frontend_url.rstrip("/")
    if view:
        url = f"{url}/?view={view}"
    webbrowser.open(url)


def ensure_local_stack(
    root: Path,
    backend_port: int = 8000,
    frontend_port: int = 5173,
    expected_version: str = "",
) -> None:
    if (root / "novelis-cargo-hub.exe").is_file() and (root / ".automacao-novelis-install").is_file():
        _ensure_hub_backend(root)
        return
    runtime = root / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    log_path = runtime / "stack-start.log"
    health = read_backend_health(backend_port)
    if health and not backend_health_ok(health, root, expected_version):
        append_stack_log(log_path, f"Backend inválido detectado na porta {backend_port}: {health}")
        stop_ports(root, backend_port, frontend_port)

    health = read_backend_health(backend_port)
    if health and backend_health_ok(health, root, expected_version) and port_open(frontend_port):
        return

    script = root / "scripts" / "run-dev.ps1"
    with log_path.open("a", encoding="utf-8", errors="replace") as log:
        log.write("\n=== Iniciando backend/frontend ===\n")
        process = subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            cwd=str(root),
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    wait_for_port(backend_port, 300, process, log_path)
    wait_for_port(frontend_port, 120, process, log_path)
    health = read_backend_health(backend_port)
    if not health or not backend_health_ok(health, root, expected_version):
        raise RuntimeError(f"Backend iniciou inválido. Health={health}. {tail_log_message(log_path)}")


def _ensure_hub_backend(root: Path) -> None:
    log_path = root / "runtime/stack-start.log"
    with log_path.open("a", encoding="utf-8") as log:
        result = subprocess.run([
            str(root / "BACKEND/.venv/Scripts/python.exe"), "-I",
            str(root / "scripts/setup/launch_backend.py"),
        ], cwd=root, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
    if result.returncode:
        raise RuntimeError("API Cargo Hub indisponivel. Consulte runtime/backend-local.log")


def restart_backend(root: Path, expected_version: str = "", backend_port: int = 8000) -> None:
    stop_ports(root, backend_port)
    ensure_local_stack(root, expected_version=expected_version)


def restart_frontend(root: Path, expected_version: str = "", frontend_port: int = 5173) -> None:
    stop_ports(root, frontend_port)
    ensure_local_stack(root, expected_version=expected_version)


def service_status(task_name: str = "AutomacaoNovelisServico") -> str:
    command = (
        "$task = Get-ScheduledTask -TaskName '" + task_name + "' -ErrorAction SilentlyContinue; "
        "if (-not $task) { 'Nao instalado'; exit 0 }; "
        "$info = Get-ScheduledTaskInfo -TaskName '" + task_name + "' -ErrorAction SilentlyContinue; "
        "$state = [string]$task.State; "
        "$last = if ($info) { [string]$info.LastTaskResult } else { '-' }; "
        "'{0} | ultimo codigo {1}' -f $state,$last"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    text = (result.stdout or result.stderr or "").strip()
    return text or "Status indisponível"


def force_stop_python_processes(root: Path) -> str:
    command = (
        "$ErrorActionPreference='SilentlyContinue'; "
        f"$current={os.getpid()}; "
        "$items = Get-Process python,pythonw -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Id -ne $current }; "
        "$count = @($items).Count; "
        "$items | Stop-Process -Force; "
        "'Processos Python finalizados: {0}' -f $count"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=str(root),
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return (result.stdout or result.stderr or "Finalização solicitada.").strip()


def read_backend_health(port: int) -> dict | None:
    if not port_open(port):
        return None
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=4) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError):
        return None


def backend_health_ok(health: dict, root: Path, expected_version: str = "") -> bool:
    if health.get("status") != "ok":
        return False
    if expected_version and str(health.get("version") or "") != expected_version:
        return False
    if health.get("playwrightDriverOk") is False:
        return False
    backend_root = str(health.get("backendRoot") or "")
    expected_backend = str((root / "BACKEND").resolve()).lower()
    if backend_root and Path(backend_root).resolve().as_posix().lower() != Path(expected_backend).as_posix():
        return False
    return True


def stop_ports(root: Path, *ports: int) -> None:
    port_text = ",".join(str(port) for port in ports)
    command = (
        "$ErrorActionPreference='SilentlyContinue'; "
        f"$ports=@({port_text}); "
        "foreach ($port in $ports) { "
        "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $port -State Listen | "
        "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }; "
        "}"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=str(root),
        capture_output=True,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    time.sleep(1)


def append_stack_log(log_path: Path, message: str) -> None:
    with log_path.open("a", encoding="utf-8", errors="replace") as log:
        log.write(f"{message}\n")


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(
    port: int,
    timeout_seconds: int,
    process: subprocess.Popen | None = None,
    log_path: Path | None = None,
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if port_open(port):
            return
        if process and process.poll() is not None and not port_open(port):
            raise RuntimeError(
                f"Porta {port} não subiu. {tail_log_message(log_path)}"
            )
        time.sleep(0.5)
    raise RuntimeError(f"Porta {port} não respondeu dentro do prazo. {tail_log_message(log_path)}")


def tail_log_message(log_path: Path | None) -> str:
    if not log_path or not log_path.exists():
        return "Log de inicialização não encontrado."
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return f"Não consegui ler o log: {log_path}"
    tail = [line for line in lines[-12:] if line.strip()]
    if not tail:
        return f"Log vazio: {log_path}"
    return f"Veja {log_path}: " + " | ".join(tail[-6:])


def request_service_stop(root: Path) -> None:
    stop_file = root / "runtime" / "desktop-service.stop"
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    stop_file.write_text("stop", encoding="utf-8")
    subprocess.run(
        ["schtasks", "/End", "/TN", "AutomacaoNovelisServico"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
