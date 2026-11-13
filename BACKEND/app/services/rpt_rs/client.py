import json
import os
import subprocess
from pathlib import Path

from app.automation.cancellable_process import run_process


class RptWorkerError(RuntimeError):
    pass


class RptWorker:
    def __init__(self, executable: Path, timeout: int = 240):
        self.executable = executable
        self.timeout = timeout

    def call(self, action: str, **payload) -> dict:
        if not self.executable.is_file():
            raise RptWorkerError("Compile o worker com scripts/build-rpt-worker.ps1.")
        try:
            result = run_process([str(self.executable)],
                input=json.dumps({"action": action, **payload}, ensure_ascii=False),
                text=True, encoding="utf-8", capture_output=True, timeout=self.timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired:
            raise RptWorkerError("Tempo limite excedido no worker rpt-rs.") from None
        except OSError:
            raise RptWorkerError("Nao foi possivel iniciar o worker rpt-rs.") from None
        try:
            response = json.loads(result.stdout)
        except ValueError:
            raise RptWorkerError("Resposta invalida do worker rpt-rs.") from None
        if result.returncode or not response.get("ok"):
            raise RptWorkerError("Worker rpt-rs: " + str(response.get("error", "falha de execucao")))
        return response
