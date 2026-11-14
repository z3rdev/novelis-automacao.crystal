import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSION_PATTERN = r"^\d+\.\d+\.\d+(?:-r[1-9]\d*)?$"


class ReleaseManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, ge=1, le=1)
    version: str = Field(pattern=VERSION_PATTERN, max_length=50)
    title: str = Field(default="Atualização do Cargo Hub", max_length=150)
    notes: str = Field(default="", max_length=10000)
    published_at: datetime
    file: str = Field(pattern=r"^NovelisCargoHubSetup-[A-Za-z0-9._-]+\.exe$", max_length=180)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    size: int = Field(gt=0, le=3 * 1024**3)
    architecture: str = Field(default="x64", pattern=r"^x64$")
    object_key: str | None = Field(default=None, max_length=280)

    @model_validator(mode="after")
    def validate_object_key(self):
        if self.object_key is not None and self.object_key != f"packages/{self.sha256.lower()}/{self.file}":
            raise ValueError("Caminho do pacote inválido.")
        return self

    def package_key(self) -> str:
        return self.object_key or self.file


def version_parts(version: str) -> tuple[int, ...]:
    if not re.fullmatch(VERSION_PATTERN, version):
        raise ValueError("Versão inválida.")
    core, _, revision = version.partition("-r")
    return (*map(int, core.split(".")), int(revision or 0))
