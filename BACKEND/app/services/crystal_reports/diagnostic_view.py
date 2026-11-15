"""Offline, escaped presentation of an existing diagnostic; never runs checks."""

import json
import re
from datetime import datetime
from html import escape
from pathlib import Path, PureWindowsPath
from zoneinfo import ZoneInfo

ASSETS = Path(__file__).with_name("diagnostic_assets")
SENSITIVE = re.compile(
    r"^(?:password|pass|pwd|senha|secret|token|pidkey|serial|authorization|api[_-]?key|private[_-]?key|credentials?)$",
    re.IGNORECASE,
)
STATES = {
    "ok": ("ok", "Verificado"),
    "already_present": ("ok", "Disponível"),
    "already_registered": ("ok", "Registrado"),
    "registered": ("ok", "Registrado"),
    "installed": ("ok", "Instalado"),
    "not_required": ("ok", "Não necessário"),
    "not_tested": ("pending", "Não testado"),
    "pending": ("pending", "Pendente"),
    "unverified": ("warning", "Não confirmado"),
    "needs_admin": ("warning", "Requer administrador"),
    "missing": ("error", "Ausente"),
    "failed": ("error", "Falhou"),
    "error": ("error", "Falhou"),
}


def sanitize(value, key=""):
    if SENSITIVE.fullmatch(key) and not isinstance(value, bool):
        return "[oculto]"
    if isinstance(value, dict):
        return {name: sanitize(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(\w+://)[^\s/@:]+:[^\s/@]+@", r"\1[oculto]@", value)
        return re.sub(
            r"(?i)\b(password|pwd|senha|pidkey|token|secret|serial)\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s;,]+)",
            r"\1=[oculto]",
            value,
        )
    return value


def state(value):
    return STATES.get(str(value or "pending"), ("pending", "Não confirmado"))


def boolean(value):
    return "ok" if value is True else "failed" if value is False else "not_tested"


def row(title, status, detail="", hint=""):
    tone, label = state(status)
    return (
        f'<div class="check-row" data-status="{tone}"><div class="check-label">'
        f'<span class="state-icon" aria-hidden="true">{"✓" if tone == "ok" else "!" if tone in {"error", "warning"} else "–"}</span>'
        f"<div><h3>{escape(str(title))}</h3>"
        f"{'<p>' + escape(str(detail)) + '</p>' if detail else ''}"
        f"{'<p class=hint>' + escape(str(hint)) + '</p>' if hint else ''}"
        f'</div></div><span class="status {tone}">{label}</span></div>'
    )


def section(title, rows):
    return f'<section><h2>{escape(title)}</h2><div class="surface">{"".join(rows)}</div></section>'


def loaded(module, title=None):
    name = title or PureWindowsPath(str(module.get("path") or "Componente nativo")).name
    info = " · ".join(
        str(part) for part in (module.get("version"), module.get("architecture")) if part
    )
    return row(
        name,
        boolean(module.get("loadable")),
        info,
        module.get("path", "")
        if module.get("loadable")
        else "Verifique a instalação do runtime x86.",
    )


def report_sections(report):
    checks = report.get("checks") or {}
    env = checks.get("environment") or {}
    engine = env.get("engine") or {}
    runtime = [
        row("Componente COM do Crystal", boolean(env.get("com_created")), env.get("prog_id", "")),
        row(
            "Processo de 32 bits",
            boolean(env.get("process_bits") == 32) if "process_bits" in env else "not_tested",
            f"Processo: {env['process_bits']} bits"
            if env.get("process_bits")
            else "Arquitetura ainda não verificada.",
        ),
        loaded(engine, "Motor de relatórios · craxddrt.dll"),
        *[loaded(module) for module in env.get("native_dlls", [])],
    ]
    if env.get("error"):
        runtime.insert(0, row("Leitura do ambiente", "failed", env["error"]))
    fonts, qr, bars = (
        checks.get(key) or {} for key in ("fonts", "qr_renderer", "code128_renderer")
    )
    database, export, symbols = (checks.get(key) or {} for key in ("database", "export", "symbols"))
    pdf = checks.get("pdf_output") or {}
    pdf_detail = (
        "Impressão pelo Windows"
        if pdf.get("engine") == "windows"
        else "Exportação nativa"
        if pdf.get("engine") == "native"
        else "Método não informado"
    )
    pdf_state = (
        boolean(pdf.get("windows_printer_available"))
        if pdf.get("engine") == "windows"
        else "ok"
        if pdf.get("engine") == "native"
        else "not_tested"
    )
    sections = [
        section("Crystal Reports RDC x86", runtime),
        section(
            "Relatório e geração do DACTE",
            [
                row(
                    "Integridade do arquivo RPT",
                    (checks.get("integrity") or {}).get("status"),
                    "Comparação com o manifesto do relatório.",
                ),
                row(
                    "Fórmulas e dados do relatório",
                    (checks.get("report") or {}).get("status"),
                    (checks.get("report") or {}).get(
                        "message", "Auditoria de fórmulas e credenciais salvas."
                    ),
                ),
                row(
                    "Fontes utilizadas",
                    fonts.get("status"),
                    "Faltando: " + ", ".join(fonts["missing"])
                    if fonts.get("missing")
                    else ", ".join(fonts.get("required", []))
                    or "Nenhuma fonte adicional informada.",
                ),
                row(
                    "QR Code",
                    qr.get("status"),
                    "Gerado em imagem pelo aplicativo."
                    if qr.get("provider") == "python"
                    else "Gerado pelo relatório.",
                ),
                row(
                    "Código de barras · Code 128",
                    bars.get("status"),
                    "Gerado em imagem pelo aplicativo."
                    if bars.get("provider") == "python"
                    else "Gerado pelo relatório.",
                ),
                row("Saída PDF", pdf_state, pdf_detail),
            ],
        ),
        section(
            "Conexão e testes com documento",
            [
                row(
                    "Provedor SQL OLE DB x86",
                    boolean(env.get("sqloledb_x86_created")),
                    "Disponibilidade do provedor de conexão.",
                ),
                row(
                    "Conexão com o SQL Server",
                    database.get("status"),
                    database.get(
                        "message",
                        "Consulta de conexão realizada."
                        if database.get("status") == "ok"
                        else "Conexão ainda não testada.",
                    ),
                ),
                row(
                    "Geração de um PDF real",
                    export.get("status"),
                    export.get(
                        "message",
                        "PDF gerado com um CT-e de teste."
                        if export.get("status") == "ok"
                        else "Gere um DACTE com filial, série e número para validar esta etapa.",
                    ),
                ),
                row(
                    "Leitura dos códigos no PDF",
                    symbols.get("status"),
                    symbols.get(
                        "message", "Comparação do QR Code e Code 128 com o XML de referência."
                    ),
                ),
                row(
                    "Validação fiscal",
                    "ok" if report.get("fiscal_validation") == "ok" else "pending",
                    "A prontidão das dependências não confirma a validação fiscal do documento.",
                ),
            ],
        ),
    ]
    preparation = report.get("preparation") or []
    if preparation:
        labels = {
            "barcodesoft": "BarcodeSoft · componente legado",
            "code128": "Fonte Code 128 · componente legado",
            "crystal": "Runtime Crystal",
            "fonts": "Fontes",
            "qr_font_registration": "Registro da fonte QR",
            "barcodesoft_registration": "Registro BarcodeSoft",
        }
        sections.append(
            section(
                "Preparação realizada",
                [
                    row(
                        labels.get(item.get("component"), item.get("component", "Componente")),
                        item.get("status"),
                        item.get("message", ""),
                    )
                    for item in preparation
                ],
            )
        )
    return "".join(sections)


def render_diagnostic(report):
    safe = sanitize(report)
    sections = report_sections(safe)
    attention = sections.count('data-status="error"') + sections.count('data-status="warning"')
    pending = sections.count('data-status="pending"')
    verified = sections.count('data-status="ok"')
    ready = safe.get("status") == "technical_ready" and attention == 0
    title = "Instalação pronta para testes" if ready else "A instalação precisa de revisão"
    try:
        checked = (
            datetime.fromisoformat(safe.get("checked_at", ""))
            .astimezone(ZoneInfo("America/Sao_Paulo"))
            .strftime("%d/%m/%Y às %H:%M")
        )
    except (ValueError, TypeError):
        checked = "Data não informada"
    data = escape(json.dumps(safe, ensure_ascii=False, indent=2))
    css = (ASSETS / "report.css").read_text(encoding="utf-8")
    script = (ASSETS / "report.js").read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><title>Diagnóstico DACTE · Cargo Hub</title>
<style>{css}</style></head><body>
<header class="topbar"><span class="brand">Cargo<span>Hub</span></span><span>Diagnóstico da instalação</span>
<button id="theme" aria-label="Alternar tema">Tema escuro</button></header>
<main><div class="page-title"><div><h1>Diagnóstico do DACTE</h1><p>Verificado em {escape(checked)} · Relatório local</p></div>
<div class="actions"><button id="copy">Copiar dados</button><button id="download">Baixar JSON</button><button id="print">Imprimir</button></div></div>
<div class="summary"><div><span class="overall {"ok" if ready else "warning"}">{title}</span><p>{verified} itens verificados · {attention} precisam de atenção · {pending} pendentes ou não testados</p></div>
<p class="production">Validação para produção: <strong>{"informada como concluída" if safe.get("production_ready") is True else "não confirmada"}</strong></p></div>
<p class="guidance">{"As dependências foram verificadas. Complete os testes com um CT-e e o XML de referência antes de homologar a geração." if ready else "Confira os itens sinalizados abaixo. Os testes não realizados permanecem identificados como pendentes."}</p>
<nav class="filters" aria-label="Filtrar verificações"><button data-filter="all" aria-pressed="true">Todos</button><button data-filter="attention" aria-pressed="false">Precisam de atenção ({attention})</button><button data-filter="pending" aria-pressed="false">Não concluídos ({pending})</button></nav>
<div id="checks">{sections}</div><p id="empty" hidden>Nenhum item neste filtro.</p>
<details class="technical"><summary>Dados técnicos do diagnóstico</summary><pre id="report-data">{data}</pre></details>
<p id="feedback" role="status" aria-live="polite"></p><footer>Este arquivo registra o resultado de uma verificação. Repita a verificação após ajustar a instalação.</footer>
</main><script>{script}</script></body></html>"""
