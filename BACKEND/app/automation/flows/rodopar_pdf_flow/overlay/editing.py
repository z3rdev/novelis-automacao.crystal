import asyncio

from playwright.async_api import Page

from app.automation.flows.rodopar_pdf_flow.overlay.replay_overlay import RodoparReplayOverlay
from app.domain.models import StepDefinition


async def edit_overlay_after_replay(
    overlay: RodoparReplayOverlay,
    page: Page,
    run_id: str,
    steps: list[StepDefinition],
) -> None:
    if not overlay.enabled or page.is_closed():
        return
    _select_current(overlay, steps)
    await overlay.update(run_id, steps, "Replay concluído. Edite, clique Salvar e depois Fechar.")
    while not page.is_closed():
        if not steps:
            await overlay.update(run_id, steps, "Mapa vazio. Use Novo, Salvar ou Fechar.")
            await asyncio.sleep(0.45)
            continue
        index = _selected_index(overlay, steps)
        step = overlay.current_step or steps[index]
        next_index = await overlay._read_once(page, run_id, steps, index, step)
        if overlay.status == "Overlay fechado.":
            return
        if next_index is not None:
            overlay.current_index = max(0, min(next_index, len(steps) - 1))
            overlay.current_step = steps[overlay.current_index]
            await overlay.update(run_id, steps)
        await asyncio.sleep(0.45)


def _select_current(overlay: RodoparReplayOverlay, steps: list[StepDefinition]) -> None:
    if not steps:
        overlay.current_index = -1
        overlay.current_step = None
        return
    overlay.current_index = _selected_index(overlay, steps)
    overlay.current_step = steps[overlay.current_index]


def _selected_index(overlay: RodoparReplayOverlay, steps: list[StepDefinition]) -> int:
    if not steps:
        return 0
    current = overlay.current_step
    if current:
        for index, step in enumerate(steps):
            if step.number == current.number:
                return index
    return max(0, min(overlay.current_index, len(steps) - 1))
