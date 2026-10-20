import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.agent.skills.contracts import SCHEMAS, Finding
from app.agent.skills.loader import SkillValidationError
from app.agent.skills.models import CORE_IDS, Selection
from app.agent.skills.registry import SkillRegistry
from app.core.config import ROOT


def test_all_definitions_have_real_contracts_and_content() -> None:
    registry = SkillRegistry.from_directory(ROOT / "extensions/skills")
    assert len(registry.all()) == 13
    for item in registry.all():
        assert len(item.instructions) > 200
        assert item.manifest.version == ("0.1.1" if item.manifest.kind == "scenario" else "0.1.0")
        assert len(item.checksum) == 64
        assert SCHEMAS[item.manifest.config_schema]().model_dump()
    assert set(CORE_IDS) == {
        "product_capability",
        "pricing_analysis",
        "user_sentiment",
        "swot_analysis",
    }


@pytest.fixture
def definitions(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    shutil.copytree(ROOT / "extensions/skills", root)
    return root


@pytest.mark.parametrize(
    "field,value",
    [
        ("allowed_tools", ["read_environment"]),
        ("output_schema", "UnknownSchema"),
        ("config_schema", "Finding"),
        ("version", "latest"),
        ("entrypoint", "../../.env"),
        ("requires", ["missing_skill"]),
    ],
)
def test_invalid_definitions_are_rejected(definitions: Path, field: str, value: object) -> None:
    path = definitions / "product_capability/manifest.yaml"
    manifest = yaml.safe_load(path.read_text("utf-8"))
    manifest[field] = value
    path.write_text(yaml.safe_dump(manifest, allow_unicode=True), "utf-8")
    with pytest.raises(SkillValidationError):
        SkillRegistry.from_directory(definitions)


def test_dependency_cycles_and_missing_skill_are_rejected(definitions: Path) -> None:
    path = definitions / "product_capability/manifest.yaml"
    manifest = yaml.safe_load(path.read_text("utf-8"))
    manifest["requires"] = ["swot_analysis"]
    path.write_text(yaml.safe_dump(manifest), "utf-8")
    with pytest.raises(SkillValidationError, match="Cyclic"):
        SkillRegistry.from_directory(definitions)


def test_guidance_change_changes_content_checksum(definitions: Path) -> None:
    before = SkillRegistry.from_directory(definitions).get("user_sentiment").checksum
    path = definitions / "user_sentiment/SKILL.md"
    path.write_text(path.read_text("utf-8") + "\n新增来源范围约束。\n", "utf-8")
    assert SkillRegistry.from_directory(definitions).get("user_sentiment").checksum != before


def test_identical_skills_have_portable_checksums_across_line_endings(definitions: Path) -> None:
    before = SkillRegistry.from_directory(definitions)
    for path in [*definitions.glob("*/manifest.yaml"), *definitions.glob("*/SKILL.md")]:
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    lf = SkillRegistry.from_directory(definitions)
    for path in [*definitions.glob("*/manifest.yaml"), *definitions.glob("*/SKILL.md")]:
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    crlf = SkillRegistry.from_directory(definitions)
    for definition in before.all():
        skill_id = definition.manifest.id
        assert lf.get(skill_id).checksum == crlf.get(skill_id).checksum
        assert lf.get(skill_id).instructions == crlf.get(skill_id).instructions


def test_client_cannot_remove_core_or_select_multiple_scenarios() -> None:
    for payload in [
        {"core_skill_ids": []},
        {"scenario_skill_id": ["ai_llm", "finance"]},
        {"advanced_skill_ids": ["market_landscape", "market_landscape"]},
    ]:
        with pytest.raises(ValidationError):
            Selection.model_validate(payload)


def test_supported_fact_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        Finding(
            statement="An unsupported fixture claim", evidence_ids=[], evidence_status="supported"
        )
