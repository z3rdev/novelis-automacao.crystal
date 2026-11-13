import re
from typing import Any

from playwright.async_api import Page


async def fill_chamado_title_message(page: Page, title: str, message: str) -> dict[str, Any]:
    result = await page.evaluate(
        """({ title, message }) => {
            const setValue = (selector, value) => {
              const el = document.querySelector(selector);
              if (!el) return false;
              el.focus?.();
              el.value = value;
              el.dispatchEvent(new Event("input", { bubbles: true }));
              el.dispatchEvent(new Event("change", { bubbles: true }));
              el.dispatchEvent(new Event("blur", { bubbles: true }));
              return true;
            };
            const escapeHtml = (value) => String(value || "")
              .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            const html = String(message || "")
              .split("\\n")
              .map((line) => line ? `<p>${escapeHtml(line)}</p>` : "<p>&nbsp;</p>")
              .join("");
            const text = String(message || "").trim();
            const report = { titleSet: false, messageSet: false, methods: [] };

            report.titleSet =
              setValue("#titulo", title) ||
              setValue('input[name="titulo"]', title) ||
              setValue('textarea[name="titulo"]', title);

            try {
              if (window.tinymce) {
                const editors = Array.from(window.tinymce.editors || []);
                const preferred = editors.filter((editor) => {
                  const id = String(editor.id || "");
                  const target = editor.getElement?.();
                  const targetName = String(target?.name || "");
                  return /mensagem|message|descricao|description/i.test(`${id} ${targetName}`);
                });
                const targets = preferred.length ? preferred : editors;
                for (const editor of targets) {
                  editor.setContent(html);
                  editor.save?.();
                  editor.fire?.("change");
                  const target = editor.getElement?.();
                  target?.dispatchEvent?.(new Event("input", { bubbles: true }));
                  target?.dispatchEvent?.(new Event("change", { bubbles: true }));
                  report.messageSet = true;
                  report.methods.push(`tinymce:${editor.id || "editor"}`);
                }
              }
            } catch (_) {}

            for (const selector of ["#mensagem", 'textarea[name="mensagem"]', 'textarea[id*="mensagem"]']) {
              if (setValue(selector, message)) {
                report.messageSet = true;
                report.methods.push(selector);
              }
            }

            for (const iframe of Array.from(document.querySelectorAll('iframe[id*="mensagem"], iframe[id$="_ifr"], iframe.tox-edit-area__iframe'))) {
              try {
                const body = iframe.contentDocument?.body;
                if (!body) continue;
                body.innerHTML = html;
                body.dispatchEvent(new Event("input", { bubbles: true }));
                body.dispatchEvent(new Event("change", { bubbles: true }));
                report.messageSet = true;
                report.methods.push(`iframe:${iframe.id || "sem-id"}`);
              } catch (_) {}
            }

            return { ...report, titleLength: String(title || "").trim().length, messageLength: text.length };
        }""",
        {"title": title, "message": message},
    )
    return result if isinstance(result, dict) else {}


async def inspect_required_fields(page: Page) -> dict[str, Any]:
    result = await page.evaluate(
        """() => {
            const textOf = (el) => String(el?.value || el?.innerText || el?.textContent || "").replace(/\\s+/g, " ").trim();
            const inputHasFile = (name) => Array.from(document.querySelectorAll(`input[name="${name}"]`))
              .some((el) => (el.files && el.files.length > 0) || String(el.value || "").trim());
            const editorTexts = [];
            try {
              if (window.tinymce) {
                for (const editor of Array.from(window.tinymce.editors || [])) {
                  editorTexts.push(String(editor.getContent?.({ format: "text" }) || ""));
                }
              }
            } catch (_) {}
            for (const iframe of Array.from(document.querySelectorAll('iframe[id*="mensagem"], iframe[id$="_ifr"], iframe.tox-edit-area__iframe'))) {
              try { editorTexts.push(String(iframe.contentDocument?.body?.innerText || "")); } catch (_) {}
            }
            for (const selector of ["#mensagem", 'textarea[name="mensagem"]', 'textarea[id*="mensagem"]']) {
              const el = document.querySelector(selector);
              if (el) editorTexts.push(textOf(el));
            }
            const title = textOf(document.querySelector("#titulo, input[name='titulo'], textarea[name='titulo']"));
            const message = editorTexts.join("\\n").replace(/\\s+/g, " ").trim();
            const missing = [];
            if (!title) missing.push("Titulo");
            if (!message) missing.push("Mensagem");
            if (!inputHasFile("arquivo[0]")) missing.push("PDF");
            if (!inputHasFile("arquivo[1]")) missing.push("XML");
            if (!inputHasFile("arquivo[2]")) missing.push("ZIP");
            return { missing, titleLength: title.length, messageLength: message.length };
        }"""
    )
    return result if isinstance(result, dict) else {"missing": []}


def is_required_form_error(result: dict[str, Any]) -> bool:
    message = str(result.get("message") or "")
    return bool(re.search(r"obrigat[oó]rio|error-focus|nao preenchid|não preenchid", message, re.I))
