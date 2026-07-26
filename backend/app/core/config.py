from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Treasury Data Alignment API"
    app_version: str = "0.1.0"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    max_upload_size_mb: int = Field(default=25, ge=1, le=100)
    allowed_extensions: tuple[str, ...] = (".csv", ".xlsx", ".xls")

    storage_dir: Path = BACKEND_ROOT / "storage"
    upload_dir: Path = BACKEND_ROOT / "storage" / "uploads"
    export_dir: Path = BACKEND_ROOT / "storage" / "exports"
    master_dir: Path = BACKEND_ROOT / "storage" / "master"

    def create_storage_directories(self) -> None:
        """Create required runtime directories when they do not exist."""

        for directory in (
            self.storage_dir,
            self.upload_dir,
            self.export_dir,
            self.master_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""

    return Settings()
