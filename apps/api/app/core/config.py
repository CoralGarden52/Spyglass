from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.agent.runtime.contracts import Role

ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://spyglass:spyglass_local@127.0.0.1:55432/spyglass"
    )
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:56379/0")
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    session_cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=86400, ge=60, le=604800)
    auth_rate_limit: int = Field(default=5, ge=1, le=100)
    auth_rate_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_namespace: str = "spyglass"
    dependency_timeout_seconds: float = Field(default=3, gt=0, le=10)
    deepseek3_api_key: SecretStr = SecretStr("")
    deepseek3_base_url: str = "https://api.deepseek.com/v1"
    deepseek3_model: str = ""
    llm_provider: Literal["deepseek", "deepseek3"] = "deepseek"
    llm_thinking: Literal["provider_default", "enabled", "disabled"] = "provider_default"
    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_max_concurrency: int = Field(default=3, ge=1, le=16)
    llm_request_timeout_seconds: int = Field(default=60, ge=5, le=180)
    # Partial overrides; omitted roles retain their bounded ModelInput defaults.
    llm_role_max_tokens: dict[Role, Annotated[int, Field(strict=True, ge=100, le=12000)]] = {}
    run_timeout_seconds: int = Field(default=240, ge=30, le=900)
    research_max_repairs: int = Field(default=2, ge=0, le=4)
    local_run_capacity: int = Field(default=2, ge=1, le=8)

    @property
    def active_model_key(self) -> SecretStr:
        return self.deepseek3_api_key if self.llm_provider == "deepseek3" else self.deepseek_api_key

    @property
    def active_model_base_url(self) -> str:
        return (
            self.deepseek3_base_url if self.llm_provider == "deepseek3" else self.deepseek_base_url
        )

    @property
    def active_model_name(self) -> str:
        return self.deepseek3_model if self.llm_provider == "deepseek3" else self.deepseek_model

    @property
    def model_configured(self) -> bool:
        return bool(
            self.active_model_key.get_secret_value()
            and self.active_model_base_url
            and self.active_model_name
        )

    @model_validator(mode="after")
    def validate_production_cookies(self) -> "Settings":
        if self.app_env == "production" and not self.session_cookie_secure:
            raise ValueError("Production requires SESSION_COOKIE_SECURE=true and HTTPS")
        return self
