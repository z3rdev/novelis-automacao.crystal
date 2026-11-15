"""Document-plan projection shared by the legacy API and persistent queue."""
from typing import Any
from app.config.settings import Settings
from app.infrastructure.json_store import read_json


def _load_plan_rows(settings: Settings, payload=None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = settings.backend_root.parent / "captures" / "pendentes" / "latest-python.json"
    if payload is None:
        payload = read_json(path, {})
    if not isinstance(payload, dict):
        payload = {}

    checked = payload.get("checked") if isinstance(payload.get("checked"), list) else []
    falta_pdf = set(payload.get("faltandoPdf") or [])
    falta_xml = set(payload.get("faltandoXml") or [])
    falta_comprovante = set(payload.get("faltandoComprovante") or [])
    pronto_chamado = set(payload.get("prontosChamado") or [])

    rows: list[dict[str, Any]] = []
    for item in checked:
        if not isinstance(item, dict):
            continue
        cte = str(item.get("cte") or "")
        row = item.get("row") if isinstance(item.get("row"), dict) else {}
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        comprovante_files = evidence.get("comprovanteFiles")
        requires_comprovante = bool(evidence.get("requiresComprovante"))
        comprovante_ok = bool(evidence.get("comprovanteOk"))
        comprovante_status = "nao_exige" if not requires_comprovante else ("ok" if comprovante_ok else "falta")
        rows.append(
            {
                "cte": cte,
                "filial": str(row.get("filial") or ""),
                "serie": str(row.get("serie") or ""),
                "documento": str(row.get("documento") or ""),
                "faltaPdf": cte in falta_pdf,
                "faltaXml": cte in falta_xml,
                "faltaComprovante": cte in falta_comprovante,
                "prontoChamado": cte in pronto_chamado,
                "pdfFile": str(evidence.get("pdfFile") or ""),
                "xmlFile": str(evidence.get("xmlFile") or ""),
                "comprovanteCount": len(comprovante_files) if isinstance(comprovante_files, list) else 0,
                "requiresComprovante": requires_comprovante,
                "hasGuia": bool(evidence.get("hasGuia")),
                "hasComprovanteFile": bool(evidence.get("hasComprovanteFile")),
                "comprovanteStatus": comprovante_status,
            }
        )

    meta = {
        "generatedAt": str(payload.get("generatedAt") or ""),
        "sourceFile": str(payload.get("sourceFile") or ""),
        "sheetName": str(payload.get("sheetName") or ""),
        "consultados": int(payload.get("consultados") or 0),
        "faltandoPdfCount": len(falta_pdf),
        "faltandoXmlCount": len(falta_xml),
        "faltandoComprovanteCount": len(falta_comprovante),
        "prontosChamadoCount": len(pronto_chamado),
    }
    return meta, rows
