from playwright.async_api import Page


OVERLAY_ROOT_ID = "rodopar-replay-overlay"


async def set_overlay_visible(page: Page, visible: bool) -> None:
    try:
        await page.evaluate(
            """payload => {
              const root = document.getElementById(payload.id);
              if (root) root.style.visibility = payload.visible ? "" : "hidden";
            }""",
            {"id": OVERLAY_ROOT_ID, "visible": visible},
        )
    except Exception:
        pass
