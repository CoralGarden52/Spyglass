from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://spyglass:spyglass_local@127.0.0.1:55432/spyglass"
    )
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:56379/0")
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    dependency_timeout_seconds: float = Field(default=3, gt=0, le=10)
    bocha_api_key: SecretStr = SecretStr("")
    bocha_base_url: str = "https://api.bocha.cn"
    bocha_web_search_endpoint: str = "/v1/web-search"
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_max_concurrency: int = Field(default=3, ge=1, le=16)
    llm_request_timeout_seconds: int = Field(default=60, ge=5, le=180)
    run_timeout_seconds: int = Field(default=240, ge=30, le=900)
