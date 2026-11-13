from pydantic import BaseModel, ConfigDict, Field


class DacteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filial: int = Field(ge=1, le=2_147_483_647)
    serie: str = Field(min_length=1, max_length=10, pattern=r"^[0-9A-Za-z]+$")
    documento: int = Field(ge=1, le=2_147_483_647)
