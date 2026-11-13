from pathlib import Path

from app.domain.models import StepCatalog, StepDefinition, StepPatch
from app.infrastructure.json_store import read_json, write_json


class StepRepository:
    def __init__(self, steps_file: Path) -> None:
        self.steps_file = steps_file

    def list(self) -> StepCatalog:
        payload = read_json(self.steps_file, {"source": "pre-passo", "steps": []})
        return StepCatalog.model_validate(payload)

    def get(self, number: int) -> StepDefinition:
        for step in self.list().steps:
            if step.number == number:
                return step
        raise KeyError(f"Passo {number} não encontrado.")

    def update(self, number: int, patch: StepPatch) -> StepDefinition:
        catalog = self.list()
        updated: StepDefinition | None = None
        steps: list[StepDefinition] = []

        for step in catalog.steps:
            if step.number != number:
                steps.append(step)
                continue

            data = step.model_dump()
            for key, value in patch.model_dump(exclude_unset=True).items():
                data[key] = value
            updated = StepDefinition(**data)
            steps.append(updated)

        if updated is None:
            raise KeyError(f"Passo {number} não encontrado.")

        catalog.steps = sorted(steps, key=lambda item: item.number)
        self.save(catalog)
        return updated

    def save(self, catalog: StepCatalog) -> None:
        write_json(self.steps_file, catalog.model_dump(mode="json"))
