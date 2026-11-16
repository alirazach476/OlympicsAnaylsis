"""Central application settings loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    project_root: Path = PROJECT_ROOT

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "olympics"
    postgres_user: str = "olympics"
    postgres_password: str = "change_me"
    database_url: str = (
        "postgresql+psycopg2://olympics:change_me@localhost:5432/olympics"
    )

    wiki_api_url: str = "https://en.wikipedia.org/w/api.php"
    wiki_user_agent: str = (
        "OlympicsHistoricalCollector/1.0 (research; contact: local-dev@example.com)"
    )
    wiki_request_delay_seconds: float = 1.0
    wiki_maxlag_seconds: int = 5
    wiki_max_retries: int = 5
    wiki_cache_dir: Path = PROJECT_ROOT / "data" / "raw" / "wikipedia" / "cache"

    crawl_max_depth: int = 3
    crawl_max_pages_per_edition: int = 500
    crawl_min_relevance_score: float = 0.45
    crawl_pause_file: Path = PROJECT_ROOT / "data" / "raw" / "wikipedia" / ".crawl_paused"
    crawl_checkpoint_every: int = 1

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    assets_root: Path = PROJECT_ROOT / "assets"
    download_images: bool = False

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def raw_wikipedia_dir(self) -> Path:
        return self.project_root / "data" / "raw" / "wikipedia"

    @property
    def reports_dir(self) -> Path:
        return self.project_root / "reports"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    try:
        settings.wiki_cache_dir.mkdir(parents=True, exist_ok=True)
        settings.raw_wikipedia_dir.mkdir(parents=True, exist_ok=True)
        (settings.raw_wikipedia_dir / "pages").mkdir(parents=True, exist_ok=True)
    except OSError:  # read-only filesystem (serverless API): the crawler cache dirs are not needed to serve data
        pass
    return settings
