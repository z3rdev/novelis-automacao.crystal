"""Local read checks only: no export, printing, portal submission or key export."""

import json
import platform
import struct
import sys
from datetime import UTC, datetime

from app.services.crystal_reports.connection import check_database, report_database
from app.services.crystal_reports.diagnostics import diagnose
from app.services.crystal_reports.service import CrystalReportService
from app.services.sefaz_certificate import select_certificate, windows_certificates


def check(identifier, title, status, message, details=None, source="live"):
    return {
        "id": identifier,
        "title": title,
        "status": status,
        "message": message,
        "details": details or {},
        "source": source,
        "checked_at": datetime.now(UTC).isoformat(),
    }


def system_check(settings):
    return check(
        "system",
        "Sistema e Python",
        "ok",
        "Ambiente do processo que atende a solicitação.",
        {
            "windows": platform.system(),
            "os_release": platform.release(),
            "python": sys.version.split()[0],
            "process_bits": struct.calcsize("P") * 8,
            "backend_root": str(settings.backend_root),
        },
    )


def certificate_check(config):
    try:
        certificates = windows_certificates()
        settings = config.xml_sefaz()
        if not settings.get("certificateCnpj") and not settings.get("certificateThumbprint"):
            return check(
                "certificate",
                "Certificado SEFAZ",
                "warning",
                "Seleção do certificado não configurada.",
                {
                    "valid_certificates_count": len(certificates),
                    "store": "CurrentUser/My",
                    "private_key_exported": False,
                },
            )
        cert = select_certificate(
            certificates,
            settings.get("certificateCnpj", ""),
            settings.get("certificateThumbprint", ""),
        )
        return check(
            "certificate",
            "Certificado SEFAZ",
            "ok",
            "Certificado válido, com chave privada associada à conta do backend.",
            {
                **cert,
                "store": "CurrentUser/My",
                "private_key_exported": False,
                "private_key_use_tested": False,
            },
        )
    except (RuntimeError, ValueError, OSError):
        return check(
            "certificate",
            "Certificado SEFAZ",
            "failed",
            "Não foi possível selecionar um certificado válido com chave privada nesta conta Windows.",
            {
                "store": "CurrentUser/My",
                "private_key_exported": False,
                "private_key_use_tested": False,
            },
        )


def crystal_checks(settings, config):
    try:
        report = diagnose(CrystalReportService(settings, config), connect=False)
        values = report.get("checks", {})
        environment = values.get("environment", {})
        design_rdc = (
            environment.get("prog_id", "").casefold() == "crystaldesignruntime.application.11"
        )
        results = [
            check(
                "crystal",
                "Crystal RDC e COM x86",
                "ok" if environment.get("compatible") and design_rdc else "failed",
                "Criação COM, arquitetura e carregamento do runtime.",
                environment,
            )
        ]
        results.append(
            check(
                "sqloledb",
                "Provedor SQLOLEDB x86",
                "ok" if environment.get("sqloledb_x86_created") else "failed",
                "Criação do provedor no processo x86; a consulta SQL é verificada separadamente.",
            )
        )
        modules = [environment["engine"]] if isinstance(environment.get("engine"), dict) else []
        for module in modules + environment.get("native_dlls", []):
            name = str(module.get("path", "")).replace("\\", "/").rsplit("/", 1)[-1]
            results.append(
                check(
                    "dll:" + name,
                    name or "DLL Crystal",
                    "ok" if module.get("loadable") else "failed",
                    "Carregamento da biblioteca no processo x86.",
                    module,
                )
            )
        titles = {
            "report": "Abertura e fórmulas do RPT",
            "integrity": "Integridade do RPT",
            "fonts": "Fontes do relatório",
            "qr_renderer": "Gerador de QR Code",
            "code128_renderer": "Gerador Code 128",
            "pdf_output": "Disponibilidade da saída PDF",
        }
        for key, title in titles.items():
            value = values.get(key)
            if value is None:
                results.append(
                    check(
                        key,
                        title,
                        "not_tested",
                        "Não verificado porque a inspeção anterior não foi concluída.",
                    )
                )
                continue
            state = value.get("status", "not_tested")
            if key == "pdf_output":
                ready = value.get("engine") == "native" or (
                    value.get("engine") == "windows" and value.get("windows_printer_available")
                )
                state = "ok" if ready else "missing"
            status = (
                "ok"
                if state == "ok"
                else "failed"
                if state in {"missing", "failed", "error"}
                else "warning"
                if state == "unverified"
                else "not_tested"
            )
            results.append(
                check(
                    key, title, status, "Disponibilidade verificada; consulte os detalhes.", value
                )
            )
        return results
    except Exception:  # noqa: BLE001 - unexpected SDK errors must yield a partial, redacted report.
        return [
            check(
                "crystal",
                "Crystal RDC e COM x86",
                "unavailable",
                "A inspeção do runtime não foi concluída.",
            )
        ]


def database_check(config):
    try:
        value = check_database(report_database(config))
        return check(
            "sql",
            "Conexão SQL do DACTE",
            "ok" if value.get("status") == "ok" else "failed",
            "Teste somente de leitura: SELECT 1.",
            value,
        )
    except Exception:  # noqa: BLE001 - driver/configuration details cannot cross this boundary.
        return check(
            "sql",
            "Conexão SQL do DACTE",
            "unavailable",
            "A conexão de leitura não pôde ser testada.",
        )


def installation_check(settings):
    path = settings.storage_dir / "installation/dacte-diagnostic.json"
    try:
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("missing_or_large")
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        # Historical evidence is explicitly distinct from the checks executed now.
        return check(
            "installation",
            "Último diagnóstico de instalação",
            "warning",
            "Registro anterior; não é uma exportação executada nesta solicitação.",
            {
                "checked_at": value.get("checked_at"),
                "status": value.get("status"),
                "export": value.get("checks", {}).get("export"),
                "symbols": value.get("checks", {}).get("symbols"),
                "fiscal_validation": value.get("fiscal_validation"),
            },
            source="installation_history",
        )
    except (OSError, ValueError, AttributeError, TypeError):
        return check(
            "installation",
            "Último diagnóstico de instalação",
            "not_tested",
            "Nenhum registro de instalação legível foi encontrado.",
            source="installation_history",
        )
