from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import ROOT, Settings


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
