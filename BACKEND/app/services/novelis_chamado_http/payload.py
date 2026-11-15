"""Prepare the configured message and validated attachments for one CT-e."""

from pathlib import Path

from app.automation.flows.novelis_chamados.controles.evidence import resolve_chamado_upload_files
from app.automation.flows.novelis_chamados.steps.novelis_support import NovelisSupport
from app.services.chamado_message import render_message
from app.services.cte_xml_files import validate_download

from . import ChamadoHttpError


def prepare_payload(cwd, config, row, output):
    evidence = config.get("evidence") or {}
    if (
        evidence.get("requiresComprovante")
        and not evidence.get("comprovanteOk")
        and not config.get("allowMissingComprovante")
    ):
        raise ChamadoHttpError("A configuração exige o comprovante pendente deste CT-e.")
    cfg = {
        **config,
        "chamadoDownloadTargetDir": str(output / "anexos"),
        "chamadoZipDir": str(output / "zip"),
    }
    files = resolve_chamado_upload_files(cwd, cfg, row)
    validate_download(Path(files["xmlFile"]), row)
    with Path(files["pdfFile"]).open("rb") as stream:
        if not stream.read(6).startswith(b"%PDF-"):
            raise ChamadoHttpError("O anexo PDF não contém um documento válido.")
    support = NovelisSupport()
    template = (
        cfg.get("chamadoMensagemComplementar")
        if support._is_complementar(row)
        else cfg.get("chamadoMensagem")
    )
    signature = str(cfg.get("chamadoAssinatura") or "")
    title = render_message(row, signature, cfg.get("chamadoTitulo") or "CTE {cte}")
    message = support.build_chamado_message(row, signature, template)
    return files, title, message
