from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    app_name: str = "Automação Novelis"
    app_env: str = "local"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_origin: str = "http://127.0.0.1:5173"
    novelis_sqlite_path: Path | None = Field(default=None, validation_alias="NOVELIS_SQLITE_PATH")

    @field_validator("novelis_sqlite_path", mode="before")
    @classmethod
    def optional_sqlite_path(cls, value):
        return value or None

    storage_dir: Path = Field(default=WORKSPACE_ROOT / "runtime")
    steps_file: Path = Field(default=BACKEND_ROOT / "app" / "data" / "steps" / "pre_passo.json")
    mapping_file: Path = Field(
        default=BACKEND_ROOT / "app" / "data" / "mappings" / "rodopar_fields.json"
    )
    legacy_project_dir: Path = Field(
        default=WORKSPACE_ROOT / "legacy",
        validation_alias="LEGACY_PROJECT_DIR",
    )

    browser_headless: bool = False
    rodopar_browser_enabled: bool = Field(default=False, validation_alias="RODOPAR_BROWSER_ENABLED")
    consulta_browser_headless: bool = Field(default=False, validation_alias="CONSULTA_BROWSER_HEADLESS")
    browser_width: int = Field(default=1024, validation_alias=AliasChoices("BROWSER_WIDTH", "WINDOW_WIDTH"))
    browser_height: int = Field(default=750, validation_alias=AliasChoices("BROWSER_HEIGHT", "WINDOW_HEIGHT"))
    browser_window_width: int = Field(default=1030, validation_alias="BROWSER_WINDOW_WIDTH")
    browser_window_height: int = Field(default=861, validation_alias="BROWSER_WINDOW_HEIGHT")
    browser_default_timeout_ms: int = 45_000
    browser_navigation_timeout_ms: int = 90_000
    browser_playwright_path: Path = Field(default=WORKSPACE_ROOT / "ms-playwright")
    tesseract_path: Path | None = Field(default=None, validation_alias="TESSERACT_PATH")
    browser_downloads_dir: Path = Field(default=WORKSPACE_ROOT / "runtime" / "downloads")
    session_reuse: bool = Field(default=True, validation_alias="SESSION_REUSE")
    session_save: bool = Field(default=True, validation_alias="SESSION_SAVE")
    session_state_file: Path = Field(default=WORKSPACE_ROOT / "runtime" / "session-state.json", validation_alias="SESSION_STATE_FILE")

    pre_url: str = "https://webcloud16.datapardc.com/"
    pre_html5_url: str = "https://webcloud16.datapardc.com/software/html5.html"
    pre_step_delay_ms: int = 800

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_origin, "http://localhost:5173", "http://127.0.0.1:1420",
                "http://localhost:1420", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]

    def ensure_directories(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.browser_downloads_dir.mkdir(parents=True, exist_ok=True)
        self.browser_playwright_path.mkdir(parents=True, exist_ok=True)

    @property
    def backend_root(self) -> Path:
        return BACKEND_ROOT


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
