import asyncio
from typing import Any

from playwright.async_api import Page


class NovelisOverlayAction(RuntimeError):
    def __init__(self, action: str) -> None:
        super().__init__(f"Acao do overlay Novelis: {action}")
        self.action = action


async def update_novelis_overlay(page: Page, state: dict[str, Any]) -> None:
    if page.is_closed():
        return
    payload = {
        "title": "Chamado Novelis",
        "cte": "",
        "phase": "",
        "message": "",
        "primaryLabel": "Continuar",
        "showPrimary": False,
        **state,
    }
    await page.evaluate(
        """(payload) => {
          const rootId = "novelis-chamado-overlay";
          let root = document.getElementById(rootId);
          if (!window.__novelisChamadoOverlay) {
            window.__novelisChamadoOverlay = { action: "", paused: false };
          }
          if (!root) {
            root = document.createElement("div");
            root.id = rootId;
            root.innerHTML = `
              <style>
                #${rootId} {
                  position: fixed; top: 12px; right: 12px; z-index: 2147483647;
                  width: 330px; font-family: Arial, Helvetica, sans-serif;
                  color: #172033; pointer-events: none;
                }
                #${rootId} .panel {
                  pointer-events: auto; background: rgba(255,255,255,.97);
                  border: 1px solid #c8d2e1; border-radius: 8px;
                  box-shadow: 0 16px 42px rgba(15,23,42,.22); overflow: hidden;
                }
                #${rootId} .head {
                  display: flex; justify-content: space-between; gap: 8px;
                  padding: 9px 10px; background: #0f172a; color: #fff;
                  font: 700 13px Arial, Helvetica, sans-serif;
                }
                #${rootId} .body {
                  padding: 10px; display: grid; gap: 8px;
                  font: 12px/1.35 Arial, Helvetica, sans-serif;
                }
                #${rootId} .line { display: flex; justify-content: space-between; gap: 10px; }
                #${rootId} .label { color: #64748b; font-weight: 700; }
                #${rootId} .value { color: #111827; font-weight: 700; text-align: right; }
                #${rootId} .message {
                  min-height: 34px; padding: 8px; border: 1px solid #d8e0ea;
                  border-radius: 6px; background: #f8fafc; color: #263241;
                  overflow-wrap: anywhere;
                }
                #${rootId} .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
                #${rootId} button {
                  min-height: 31px; border: 1px solid #c8d2e1; border-radius: 6px;
                  background: #fff; color: #1e293b; font-weight: 700;
                  font-size: 12px; cursor: pointer;
                }
                #${rootId} button.primary { background: #2563eb; border-color: #2563eb; color: #fff; }
                #${rootId} button.danger { background: #b91c1c; border-color: #b91c1c; color: #fff; }
              </style>
              <div class="panel">
                <div class="head">
                  <span data-role="title"></span>
                  <span data-role="phase"></span>
                </div>
                <div class="body">
                  <div class="line"><span class="label">CTE</span><span class="value" data-role="cte"></span></div>
                  <div class="message" data-role="message"></div>
                  <div class="actions">
                    <button class="primary" data-role="primary"></button>
                    <button data-role="pause"></button>
                    <button class="danger" data-action="stop">Parar</button>
                    <button data-action="hide">Ocultar</button>
                  </div>
                </div>
              </div>`;
            document.documentElement.appendChild(root);
            root.querySelector('[data-role="primary"]').onclick = () => {
              window.__novelisChamadoOverlay.action = "continue";
            };
            root.querySelector('[data-role="pause"]').onclick = () => {
              window.__novelisChamadoOverlay.paused = !window.__novelisChamadoOverlay.paused;
            };
            root.querySelector('[data-action="stop"]').onclick = () => {
              window.__novelisChamadoOverlay.action = "stop";
            };
            root.querySelector('[data-action="hide"]').onclick = () => {
              root.style.display = "none";
            };
          }
          root.style.display = "";
          const setText = (role, value) => {
            const el = root.querySelector(`[data-role="${role}"]`);
            if (el) el.textContent = String(value || "");
          };
          const primary = root.querySelector('[data-role="primary"]');
          const pause = root.querySelector('[data-role="pause"]');
          setText("title", payload.title);
          setText("phase", payload.phase);
          setText("cte", payload.cte);
          setText("message", payload.message);
          if (primary) {
            primary.textContent = String(payload.primaryLabel || "Continuar");
            primary.style.display = payload.showPrimary ? "" : "none";
          }
          if (pause) {
            pause.textContent = window.__novelisChamadoOverlay.paused ? "Retomar" : "Pausar";
          }
        }""",
        payload,
    )


async def read_novelis_overlay_control(page: Page) -> dict[str, Any]:
    try:
        return await page.evaluate(
            """() => {
              const overlay = window.__novelisChamadoOverlay || { action: "", paused: false };
              const action = String(overlay.action || "");
              overlay.action = "";
              return { action, paused: Boolean(overlay.paused) };
            }"""
        )
    except Exception:
        return {"action": "", "paused": False}


async def wait_if_novelis_paused(page: Page, state: dict[str, Any], poll_ms: int = 250) -> None:
    while True:
        control = await read_novelis_overlay_control(page)
        if control.get("action") == "stop":
            raise NovelisOverlayAction("stop")
        if not control.get("paused"):
            return
        await update_novelis_overlay(page, {**state, "message": "Automação pausada pelo overlay."})
        await asyncio.sleep(poll_ms / 1000)
