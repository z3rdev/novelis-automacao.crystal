"""Child entry point. Frames contain only sanitized diagnostic data."""

import argparse
import json
import sqlite3
import time
from datetime import UTC, datetime

from app.api.routers.health import _read_release_version
from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.domain.remote_diagnostics import DiagnosticOptions
from app.infrastructure.operations_store import OperationsStore
from app.services.device_identity import device_identity
from app.services.remote_diagnostics.checks import (
    certificate_check,
    check,
    crystal_checks,
    database_check,
    installation_check,
    system_check,
)
from app.services.remote_diagnostics.history import collect_history
from app.services.remote_diagnostics.redaction import Redactor

FRAME = "DIAGNOSTIC_RESULT="


def collect(settings, config, options, emit=lambda report: None):
    started = time.monotonic()
    redactor = Redactor(config)
    identity = device_identity()
    identity.pop("mac_addresses", None)
    report = {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "complete": False,
        "device": {**identity, "version": _read_release_version(settings.backend_root.parent)},
        "scope": options.model_dump(),
        "checks": [],
        "runs": [],
        "http": [],
        "summary": {},
        "limitations": [
            "Nenhum chamado enviado, PDF gerado ou chave privada exportada nesta coleta.",
            "O HTTP apresentado é evidência das execuções anteriores, não um novo envio ao portal.",
        ],
    }

    def checkpoint():
        failed = sum(run.get("status") == "failed" for run in report["runs"])
        confirmed = len(
            {
                str(
                    item["details"].get("number")
                    or item["details"].get("numeroChamado")
                    or (item["details"].get("run_id"), item["details"].get("cte"))
                )
                for item in report["http"]
                if item["details"].get("status") == "confirmed"
            }
        )
        report["summary"] = {
            "runs": len(report["runs"]),
            "failed_runs": failed,
            "cancelled_runs": sum(run.get("status") == "cancelled" for run in report["runs"]),
            "http_events": len(report["http"]),
            "confirmed_tickets": confirmed,
            "issues": sum(
                item["status"] in {"failed", "warning", "unavailable"} for item in report["checks"]
            ),
        }
        report["duration_seconds"] = round(time.monotonic() - started, 2)
        sanitized = redactor.clean(report)
        # Keep each stdout frame below the parent's bound even with verbose histories.
        while len(json.dumps(sanitized, ensure_ascii=True)) > 1_500_000:
            largest = max(sanitized["runs"], key=lambda run: len(run["events"]), default=None)
            if largest and largest["events"]:
                largest["events"] = largest["events"][: len(largest["events"]) // 2]
                largest["events_truncated"] = sanitized["events_truncated"] = True
            elif sanitized["http"]:
                sanitized["http"] = sanitized["http"][: len(sanitized["http"]) // 2]
                sanitized["http_truncated"] = True
            else:
                break
        emit(sanitized)

    report["checks"].append(system_check(settings))
    checkpoint()
    store = OperationsStore(settings.novelis_sqlite_path) if settings.novelis_sqlite_path else None
    try:
        if store and store.path.is_file():
            config.values.update(store.preferences())
            redactor = Redactor(config)
        history = collect_history(store, options, redactor)
        report.update({key: history[key] for key in ("runs", "http", "events_truncated")})
        report["http_truncated"] = history.get("http_truncated", False)
        report["checks"].append(
            check(
                "history",
                "Últimas execuções",
                "ok" if history["available"] else "unavailable",
                "Histórico desta máquina; a ausência de eventos não comprova sucesso.",
                source="execution_history",
            )
        )
    except (OSError, RuntimeError, ValueError, sqlite3.Error):
        report["checks"].append(
            check(
                "history",
                "Últimas execuções",
                "unavailable",
                "Não foi possível ler o histórico desta máquina.",
                source="execution_history",
            )
        )
    checkpoint()
    report["checks"].append(certificate_check(config))
    checkpoint()
    report["checks"].extend(crystal_checks(settings, config))
    checkpoint()
    report["checks"].append(database_check(config))
    checkpoint()
    report["checks"].append(installation_check(settings))
    report["checks"].append(
        check(
            "fiscal_export",
            "Nova exportação e leitura dos códigos",
            "not_tested",
            "A coleta remota não gera documentos. QR, Code 128 e impressão completa exigem teste fiscal separado.",
        )
    )
    report["complete"] = True
    checkpoint()
    return redactor.clean(report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-runs", type=int, required=True)
    parser.add_argument("--days-back", type=int, required=True)
    args = parser.parse_args()
    settings = Settings()

    def emit(report):
        print(FRAME + json.dumps(report, ensure_ascii=True, separators=(",", ":")), flush=True)

    collect(
        settings,
        LegacyConfig(settings),
        DiagnosticOptions(max_runs=args.max_runs, days_back=args.days_back),
        emit,
    )


if __name__ == "__main__":
    main()
