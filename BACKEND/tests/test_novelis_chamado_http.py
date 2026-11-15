import asyncio
import json

import httpx
import pytest

from app.services.novelis_chamado_http import ChamadoHttpError, prepare, submit_once

CTE = "8-10-1559"
NUMBER = "20261114999999"
FORM = """<form id="form" action="/portal/chamado" method="POST">
<input name="unique_number" type="hidden" value="private-nonce">
<input name="_token" type="hidden" value="private-token">
<input name="id" type="hidden" value="">
<input name="button" id="button" type="hidden" value="">
<select name="tipo_chamado_id"><option value=""></option>
<option value="0;36">AF.001 - Auditoria de Frete</option></select>
<input name="titulo" required><textarea name="mensagem"></textarea>
<button id="salvar" name="salvar" value="Abrir Chamado" type="button">Abrir</button>
</form>"""
FRAGMENT = """<select name="empresa_relacionada"><option value="1" selected>Empresa</option></select>
<input type="file" name="arquivo[0]" class="required-file" data-allowed-file-extensions="pdf">
<input type="file" name="arquivo[1]" class="required-file" data-allowed-file-extensions="xml">
<input type="file" name="arquivo[2]" data-allowed-file-extensions="zip">
<input name="arquivo_form_content[0]" type="hidden" value="">
<input name="arquivo_form_content[1]" type="hidden" value="">
<input name="arquivo_form_content[2]" type="hidden" value="">"""


def uploads(tmp_path):
    values = {
        "pdfFile": "CTRC_8-10-1559.pdf",
        "xmlFile": "CTE_8-10-1559.xml",
        "zipFile": "tarifa-1.zip",
    }
    for key, name in values.items():
        path = tmp_path / name
        path.write_bytes(b"test fixture")
        values[key] = path
    return values


def portal_calls(outcome, fragment=FRAGMENT, readback=None):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/ajax/chamado":
            assert request.headers["x-xsrf-token"] == "csrf-cookie"
            assert request.content == b"tipo_chamado_id=36&form_content="
            return httpx.Response(200, text=fragment)
        if request.url.path == "/portal/chamado/":
            return httpx.Response(200, text=FORM)
        if request.method == "POST":
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        content = readback or (
            f"<h2>Chamado número {NUMBER}</h2><p>CT-e {CTE}</p>"
            "<p>CTRC_8-10-1559.pdf CTE_8-10-1559.xml tarifa-1.zip</p>"
        )
        return httpx.Response(200, text=content)

    return handler, calls


async def run_test(tmp_path, handler):
    async with httpx.AsyncClient(
        base_url="https://novelis.wtmh.com.br",
        transport=httpx.MockTransport(handler),
        cookies={"XSRF-TOKEN": "csrf-cookie"},
    ) as client:
        prepared = await prepare(
            client, {}, "Título", "CT-e 8-10-1559\n<mensagem>", uploads(tmp_path)
        )
        assert "private-token" not in repr(prepared)
        return await submit_once(client, prepared, CTE)


def test_sends_original_nonce_button_and_three_files_then_verifies_readback(tmp_path):
    handler, calls = portal_calls(
        httpx.Response(303, headers={"location": f"/portal/chamado/{NUMBER}"})
    )
    result = asyncio.run(run_test(tmp_path, handler))
    assert result["status"] == "confirmed" and result["attachments_visible"]
    save = next(item for item in calls if item.url.path == "/portal/chamado")
    assert save.headers["content-type"].startswith("multipart/form-data")
    assert b'filename="CTRC_8-10-1559.pdf"' in save.content
    assert b'filename="CTE_8-10-1559.xml"' in save.content
    assert b'filename="tarifa-1.zip"' in save.content
    assert b'name="salvar"\r\n\r\nAbrir Chamado' in save.content
    assert b'name="button"' not in save.content
    assert b"private-nonce" in save.content and b"private-token" in save.content
    assert b"&lt;mensagem&gt;" in save.content
    assert len(calls) == 4


def test_duplicate_response_is_not_a_new_ticket(tmp_path):
    handler, calls = portal_calls(
        httpx.Response(200, text=f"CT-e já está cadastrado no chamado número {NUMBER}")
    )
    result = asyncio.run(run_test(tmp_path, handler))
    assert result["status"] == "duplicate" and result["number"] == NUMBER
    assert len(calls) == 3


@pytest.mark.parametrize(
    "outcome",
    [
        httpx.ReadTimeout("test timeout"),
        httpx.Response(500),
        httpx.Response(200, text="Sem confirmação"),
    ],
)
def test_uncertain_save_is_never_retried(tmp_path, outcome):
    handler, calls = portal_calls(outcome)
    result = asyncio.run(run_test(tmp_path, handler))
    assert result["status"] == "indeterminate"
    assert len([item for item in calls if item.url.path == "/portal/chamado"]) == 1


def test_does_not_follow_cross_origin_redirect(tmp_path):
    handler, calls = portal_calls(
        httpx.Response(302, headers={"location": f"https://other.example/portal/chamado/{NUMBER}"})
    )
    result = asyncio.run(run_test(tmp_path, handler))
    assert result["status"] == "indeterminate" and len(calls) == 3
    assert all(item.url.host == "novelis.wtmh.com.br" for item in calls)


def test_readback_must_match_the_exact_cte(tmp_path):
    handler, _ = portal_calls(
        httpx.Response(303, headers={"location": f"/portal/chamado/{NUMBER}"}),
        readback=f"Chamado número {NUMBER} CT-e 8-10-15591",
    )
    assert asyncio.run(run_test(tmp_path, handler))["status"] == "indeterminate"


def test_new_required_field_stops_before_saving(tmp_path):
    handler, calls = portal_calls(
        httpx.Response(200), fragment=FRAGMENT + '<input name="form[extra]" required>'
    )
    with pytest.raises(ChamadoHttpError, match="obrigatórios"):
        asyncio.run(run_test(tmp_path, handler))
    assert len(calls) == 2


@pytest.mark.parametrize(
    "content",
    [
        f'<script>location.href="/portal/chamado/{NUMBER}"</script>',
        json.dumps({"message": f"Chamado de número {NUMBER}"}),
    ],
)
def test_http_200_confirmation_accepts_portal_redirect_scripts_and_json(tmp_path, content):
    handler, _ = portal_calls(httpx.Response(200, text=content))
    assert asyncio.run(run_test(tmp_path, handler))["status"] == "confirmed"


def test_renamed_portal_attachment_links_are_verified(tmp_path):
    html = (
        f"<h2>Resumo do chamado {NUMBER}</h2><p>CT-e {CTE}</p>"
        '<a href="/files/583565_ctrc-8-10-1559_761.pdf&download=false">PDF</a>'
        '<a href="/files/583565_cte-8-10-1559_919.xml">XML</a>'
        '<a href="/files/583565_tarifa-1_452.zip">ZIP</a>'
    )
    handler, _ = portal_calls(
        httpx.Response(303, headers={"location": f"/portal/chamado/{NUMBER}"}), readback=html
    )
    result = asyncio.run(run_test(tmp_path, handler))
    assert result["status"] == "confirmed" and result["attachments_visible"]
