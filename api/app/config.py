"""Application configuration loaded from environment variables.

Every model and registry source is configurable through the environment. Nothing is
hardcoded. When META_API_KEY is unset the whole system runs in MOCK mode.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    env = os.environ.get("HASKE_DATA_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1] / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Meta Model API (OpenAI-compatible).
    meta_api_base_url: str = "https://api.meta.ai/v1"
    meta_api_key: str = ""
    meta_vision_model: str = "muse-spark-1.3"

    # Registry sources.
    greenbook_base_url: str = "https://greenbook.nafdac.gov.ng"
    napams_base_url: str = "https://registration.nafdac.gov.ng"

    # Local storage.
    data_dir: Path = _default_data_dir()

    # Politeness knobs.
    request_delay_seconds: float = 2.0
    request_timeout_seconds: float = 30.0
    snapshot_min_ratio: float = 0.8

    @property
    def snapshots_dir(self) -> Path:
        return self.data_dir / "snapshots"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "haske.db"

    @property
    def mock_mode(self) -> bool:
        return not self.meta_api_key

    @property
    def user_agent(self) -> str:
        return "Haske/0.1 (product-authenticity checker; +https://github.com/emperorsixpacks/haske)"


def get_settings() -> Settings:
    return Settings()
