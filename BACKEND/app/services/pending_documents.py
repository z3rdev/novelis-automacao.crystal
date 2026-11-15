"""Recheck existing plan rows against the configured document directories."""

from copy import deepcopy
from pathlib import Path

from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder
from app.services.document_index import DocumentIndex
from app.services.document_scan import scan_evidence


def refresh_files(payload: dict, config, root: Path) -> dict:
    result = deepcopy(payload)
    policy = config.get("NOVELIS_CHAMADO_ALLOW_MISSING_COMPROVANTE")
    result["skipChamadoMissingComprovante"] = str(policy).lower() not in {"true", "1", "sim", "yes"}
    builder = PendentesPlanBuilder(
        root, None, cache_directories=True, document_index=DocumentIndex()
    )
    pdf, xml, proofs = config.rodopar_pdf(), config.xml_sefaz(), config.comprovante_local()
    missing_pdf, missing_xml, missing_proofs, ready = [], [], [], []
    items = result.get("checked", [])
    evidence_rows = scan_evidence(builder, [item["row"] for item in items], pdf, xml, proofs)
    for item, evidence in zip(items, evidence_rows):
        item["evidence"] = evidence
        if not evidence["pdfFile"]:
            missing_pdf.append(item["cte"])
        if not evidence["xmlFile"]:
            missing_xml.append(item["cte"])
        documents_ok = bool(evidence["pdfFile"] and evidence["xmlFile"])
        if documents_ok and not evidence["comprovanteOk"]:
            missing_proofs.append(item["cte"])
        if documents_ok and (
            evidence["comprovanteOk"] or not result.get("skipChamadoMissingComprovante", True)
        ):
            ready.append(item["cte"])
    result.update(
        faltandoPdf=missing_pdf,
        faltandoXml=missing_xml,
        faltandoComprovante=missing_proofs,
        prontosChamado=ready,
    )
    return result
