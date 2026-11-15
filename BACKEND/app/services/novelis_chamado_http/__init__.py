"""Opt-in HTTP test of the portal's existing multipart opening form."""

import json
import re
from contextlib import ExitStack
from dataclasses import dataclass, field
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from app.automation.flows.novelis_chamados.controles.save import (
    DUPLICATE_CHAMADO_PATTERN,
    extract_chamado_numero,
)
from app.services.novelis_report_http import ORIGIN

from .form import Form

OPENING = "/portal/chamado/"
UPLOADS = {"arquivo[0]": "pdfFile", "arquivo[1]": "xmlFile", "arquivo[2]": "zipFile"}
MIME = {".pdf": "application/pdf", ".xml": "text/xml", ".zip": "application/zip"}


class ChamadoHttpError(RuntimeError):
    """A sanitized pre-submission error suitable for a diagnostic log."""


@dataclass(repr=False)
class Prepared:
    action: str
    fields: dict = field(repr=False)
    uploads: dict = field(repr=False)


def headers(client, *, ajax=False):
    result = {"Referer": ORIGIN + OPENING}
    if ajax:
        result["X-Requested-With"] = "XMLHttpRequest"
    if token := client.cookies.get("XSRF-TOKEN"):
        result["X-XSRF-TOKEN"] = unquote(token)
    return result


async def load_form(client, config):
    response = await client.get(OPENING)
    if response.status_code != 200:
        raise ChamadoHttpError("O portal não entregou o formulário autenticado.")
    form = Form()
    form.feed(response.text)
    target = response.url.join(form.action)
    if (
        str(target).rstrip("/") != ORIGIN + "/portal/chamado"
        or form.method != "POST"
        or form.fields.get("id")
        or not {"titulo", "mensagem", "unique_number"} <= form.fields.keys()
        or "salvar" not in form.buttons
    ):
        raise ChamadoHttpError("O formulário de abertura mudou ou a sessão não foi confirmada.")
    expected = config.get("chamadoItem") or "AF.001 - Auditoria de Frete"
    option = next(
        (
            item
            for item in form.options.get("tipo_chamado_id", [])
            if item["text"].strip() == expected and item["value"].startswith("0;")
        ),
        None,
    )
    if not option:
        raise ChamadoHttpError("O tipo de abertura configurado não está disponível para a conta.")
    response = await client.post(
        "/ajax/chamado",
        data={"tipo_chamado_id": option["value"].split(";")[1], "form_content": ""},
        headers=headers(client, ajax=True),
    )
    if response.status_code != 200:
        raise ChamadoHttpError("O portal não entregou os campos de anexos.")
    dynamic = Form(fragment=True)
    dynamic.feed(response.text)
    if dynamic.files.keys() != UPLOADS.keys() or not dynamic.fields.get("empresa_relacionada"):
        raise ChamadoHttpError("Os anexos ou a empresa do formulário exigem revisão.")
    return form, dynamic, option["value"], str(target)


async def prepare(client, config, title, message, uploads):
    form, dynamic, selected_type, target = await load_form(client, config)
    paths = {name: Path(uploads[key]) for name, key in UPLOADS.items()}
    for name, path in paths.items():
        if not path.is_file() or not path.stat().st_size:
            raise ChamadoHttpError("Um dos anexos preparados está ausente ou vazio.")
        extensions = dynamic.files[name]
        expected_extension = {"arquivo[0]": ".pdf", "arquivo[1]": ".xml", "arquivo[2]": ".zip"}[
            name
        ]
        if path.suffix.lower() != expected_extension or (
            extensions and path.suffix.lstrip(".").lower() not in extensions
        ):
            raise ChamadoHttpError("A extensão de um anexo não é aceita pelo formulário.")
    values = {
        **form.fields,
        **dynamic.fields,
        "tipo_chamado_id": selected_type,
        "titulo": title.strip(),
        "mensagem": "".join(
            f"<p>{escape(line, quote=False)}</p>" if line else "<p>&nbsp;</p>"
            for line in message.split("\n")
        ),
    }
    # The portal renames this hidden control to the clicked button's name.
    values.pop("button", None)
    name, value = form.buttons["salvar"]
    values[name] = value
    missing = (form.required | dynamic.required) - paths.keys()
    if not title.strip() or not message.strip() or any(not values.get(key) for key in missing):
        raise ChamadoHttpError("Há campos obrigatórios sem preenchimento no formulário.")
    return Prepared(str(target), values, paths)


def ticket_path(location):
    url = urlsplit(str(httpx.URL(ORIGIN + OPENING).join(location)))
    if url.scheme != "https" or url.netloc != urlsplit(ORIGIN).netloc:
        return ""
    match = re.fullmatch(r"/portal/chamado/(\d{4,})/?", url.path)
    return match.group(1) if match else ""


class AttachmentLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = []

    def handle_starttag(self, tag, attrs):
        if tag == "a" and (href := dict(attrs).get("href")):
            self.names.append(unquote(urlsplit(href).path).rsplit("/", 1)[-1].split("&")[0])


async def verify_ticket(client, number, cte, uploads, result):
    try:
        check = await client.get(f"/portal/chamado/{number}", follow_redirects=False)
    except httpx.HTTPError:
        return result
    result = {**result, "number": number, "readback_http": check.status_code}
    content = unescape(re.sub(r"<[^>]+>", " ", check.text))
    if (
        check.status_code != 200
        or extract_chamado_numero(content) != number
        or not re.search(r"(?<![\d-])" + re.escape(cte) + r"(?![\d-])", content)
    ):
        return result
    links = AttachmentLinks()
    links.feed(check.text)
    matched = []
    for path in uploads.values():
        stem = r"[-_]".join(map(re.escape, re.split(r"[-_]", path.stem.casefold())))
        pattern = r"(?:^|[_-])" + stem + r"(?:[_-]\d+)?" + re.escape(path.suffix.casefold()) + "$"
        matched.append(
            path.name in content or any(re.search(pattern, name.casefold()) for name in links.names)
        )
    return {
        **result,
        "status": "confirmed",
        "attachments_visible": all(matched),
        "url": ORIGIN + f"/portal/chamado/{number}",
    }


async def submit_once(client, prepared, cte):
    """Return uncertainty on transport/confirmation errors. Never repeat a save POST."""
    content = unescape(prepared.fields.get("mensagem", ""))
    if not re.fullmatch(r"\d+-\d+-\d+", cte) or not re.search(
        r"(?<![\d-])" + re.escape(cte) + r"(?![\d-])", content
    ):
        raise ChamadoHttpError("A mensagem preparada não identifica o CT-e escolhido.")
    try:
        with ExitStack() as stack:
            files = {
                name: (path.name, stack.enter_context(path.open("rb")), MIME[path.suffix.lower()])
                for name, path in prepared.uploads.items()
            }
            response = await client.post(
                prepared.action,
                data=prepared.fields,
                files=files,
                headers=headers(client),
                timeout=120,
                follow_redirects=False,
            )
    except (httpx.HTTPError, OSError):
        return {"status": "indeterminate", "save_http": None, "submitted": True}
    result = {"status": "indeterminate", "save_http": response.status_code, "submitted": True}
    text = response.text
    if text.lstrip().startswith(("{", "[")):
        try:
            text = json.dumps(response.json(), ensure_ascii=False)
        except ValueError:
            pass
    text = unescape(text)
    if DUPLICATE_CHAMADO_PATTERN.search(text):
        return {**result, "status": "duplicate", "number": extract_chamado_numero(text)}
    if response.status_code not in {200, 201, 302, 303}:
        return result
    location = response.headers.get("location", "")
    number = ticket_path(location) if location else extract_chamado_numero(text)
    if not number:
        candidates = re.findall(r'(?:https?://[^\s"\x27<>]+)?/portal/chamado/\d{4,}', text)
        number = next((value for url in candidates if (value := ticket_path(url))), "")
    if not number:
        return result
    return await verify_ticket(client, number, cte, prepared.uploads, result)
