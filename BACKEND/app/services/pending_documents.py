"""Recheck existing plan rows against the configured document directories."""
from copy import deepcopy
from pathlib import Path

from app.automation.flows.pendentes.controles.plan import PendentesPlanBuilder


def refresh_files(payload: dict, config, root: Path) -> dict:
    result = deepcopy(payload)
    builder = PendentesPlanBuilder(root, None, cache_directories=True)
    pdf, xml, proofs = config.rodopar_pdf(), config.xml_sefaz(), config.comprovante_local()
    for value in (pdf.get("downloadTargetDir"), xml.get("downloadDir"), proofs.get("targetDir")):
        if value:
            directory = Path(value)
            if directory.is_absolute():
                accessible = directory.is_dir()
                if str(directory).startswith("\\\\") and not accessible:
                    raise OSError("Pasta configurada de documentos indisponivel.")
    missing_pdf, missing_xml, missing_proofs, ready = [], [], [], []
    for item in result.get("checked", []):
        row = item["row"]
        evidence = builder.resolve_evidence(row, pdf, xml, proofs)
        item["evidence"] = evidence
        if not evidence["pdfFile"]:
            missing_pdf.append(item["cte"])
        if not evidence["xmlFile"]:
            missing_xml.append(item["cte"])
        documents_ok = bool(evidence["pdfFile"] and evidence["xmlFile"])
        if documents_ok and not evidence["comprovanteOk"]:
            missing_proofs.append(item["cte"])
        if documents_ok and (evidence["comprovanteOk"] or not result.get("skipChamadoMissingComprovante", True)):
            ready.append(item["cte"])
    result.update(faltandoPdf=missing_pdf, faltandoXml=missing_xml,
                  faltandoComprovante=missing_proofs, prontosChamado=ready)
    return result
