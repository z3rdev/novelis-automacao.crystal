from collections.abc import Awaitable, Callable

from app.automation.steps.step_runner import StepRunner
from app.config.settings import Settings
from app.domain.models import RunStartRequest, StepDefinition
from app.domain.run_state import RunState
from app.infrastructure.event_bus import EventBus
from app.services.browser_driver import BrowserDriver
from app.services.step_repository import StepRepository


ShouldStop = Callable[[], bool]


class PrePassoFlow:
    def __init__(
        self,
        settings: Settings,
        repository: StepRepository,
        event_bus: EventBus,
        run_state: RunState,
        should_stop: ShouldStop,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.event_bus = event_bus
        self.run_state = run_state
        self.should_stop = should_stop

    async def run(
        self,
        request: RunStartRequest,
        run_id: str,
        browser: BrowserDriver | None,
    ) -> None:
        steps = self._select_steps(request.max_steps)
        runner = StepRunner(self.settings, self.event_bus.publish)

        if not request.dry_run and browser is not None:
            await self.event_bus.publish(
                "Abrindo DataPar HTML5 no navegador.",
                run_id=run_id,
                kind="browser.open",
                payload={"url": self.settings.pre_html5_url},
            )
            await browser.open_url(self.settings.pre_html5_url)

        for step in steps:
            if self.should_stop():
                await self.event_bus.publish(
                    "Fluxo interrompido antes do proximo passo.",
                    run_id=run_id,
                    level="warn",
                    kind="run.stop",
                )
                return
            await self.run_state.update(current_step=step.number, message=step.label)
            await runner.execute(step, request, browser, run_id)

    def _select_steps(self, max_steps: int | None) -> list[StepDefinition]:
        steps = [step for step in self.repository.list().steps if step.enabled]
        if max_steps is None:
            return steps
        return steps[:max_steps]
