from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import ROOT, Settings


def test_explicit_model_provider_selects_its_own_configuration():
    settings = Settings(
        _env_file=None,
        llm_provider="deepseek3",
        deepseek_api_key="unused",
        deepseek3_api_key="selected-test-key",
        deepseek3_model="selected-model",
        deepseek3_base_url="https://models.example/v1",
    )
    assert settings.active_model_key.get_secret_value() == "selected-test-key"
    assert settings.active_model_base_url == "https://models.example/v1"
    assert settings.active_model_name == "selected-model"
    assert settings.model_configured
    assert settings.model_copy(update={"deepseek3_model": ""}).model_configured is False


def test_environment_file_is_resolved_from_repository_root() -> None:
    assert ROOT == Path(__file__).resolve().parents[4]
    assert (ROOT / "prompt.md").is_file()


def test_settings_never_expose_secrets_in_repr() -> None:
    settings = Settings(_env_file=None, deepseek_api_key="test-only-private-value")
    assert "test-only-private-value" not in repr(settings)


@pytest.mark.parametrize("limit", [0, 17])
def test_concurrency_bounds_reject_invalid_values(limit: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_max_concurrency=limit)


def test_production_requires_secure_session_cookies() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", session_cookie_secure=False)
    assert Settings(
        _env_file=None, app_env="production", session_cookie_secure=True
    ).session_cookie_secure
