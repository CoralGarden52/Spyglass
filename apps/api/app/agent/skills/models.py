from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.schemas import Mode, Scenario

CORE_IDS = ("product_capability", "pricing_analysis", "user_sentiment", "swot_analysis")
SCENARIO_IDS = (
    "general_analysis",
    "ecommerce",
    "internet_product",
    "hardware_iot",
    "ai_llm",
    "finance",
)
ADVANCED_IDS = ("market_landscape", "business_model", "strategic_recommendation")
TOOL_WHITELIST = frozenset(
    {"deepseek_search", "bocha_search", "web_fetch", "evidence_search", "knowledge_retrieval"}
)
AdvancedID = Literal["market_landscape", "business_model", "strategic_recommendation"]
SkillKind = Literal["scenario", "core", "advanced"]


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1]
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=10, max_length=300)
    version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
    kind: SkillKind
    entrypoint: Literal["SKILL.md"]
    applies_to: tuple[Literal["planner", "collector", "analyst", "writer", "reviewer"], ...] = (
        Field(min_length=1)
    )
    requires: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    input_schema: str
    output_schema: str
    config_schema: str
    dimensions: tuple[str, ...] = Field(min_length=1)
    source_priorities: tuple[str, ...] = Field(min_length=1)
    review_aspects: tuple[str, ...] = Field(min_length=1)
    recommended_advanced: dict[Mode, tuple[AdvancedID, ...]]


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Mode = "standard"
    scenario_skill_id: Scenario = "general_analysis"
    advanced_skill_ids: list[AdvancedID] = Field(default_factory=list, max_length=3)
    advanced_skill_selection: Literal["manual", "auto"] = "manual"

    @field_validator("advanced_skill_ids")
    @classmethod
    def no_duplicates(cls, value: list[AdvancedID]) -> list[AdvancedID]:
        if len(value) != len(set(value)):
            raise ValueError("Duplicate advanced skills")
        return value


class SkillView(BaseModel):
    id: str
    name: str
    description: str
    kind: SkillKind
    version: str
    schema_version: Literal[1] = 1
    manifest_checksum: str
    is_system_required: bool
    enabled: bool
    revision: int
    config_version: str
    config_status: Literal["current", "migration_required"] = "current"
    config: dict[str, Any]
    allowed_tools: list[str]
    applies_to: list[str]
    requires: list[str]
    dimensions: list[str]


class SkillDetail(SkillView):
    instructions: str
    input_json_schema: dict[str, Any]
    output_json_schema: dict[str, Any]
    config_json_schema: dict[str, Any]


class SkillList(BaseModel):
    schema_version: Literal[1] = 1
    data: list[SkillView]


class SkillResult(BaseModel):
    schema_version: Literal[1] = 1
    data: SkillDetail


class ConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    config: dict[str, Any] | None = None
    expected_revision: int = Field(ge=0)


class Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: Literal[1] = 1
    id: str
    kind: SkillKind
    version: str
    manifest_checksum: str
    selection_source: Literal["manual", "auto", "required"]
    selection_reason: str
    config: dict[str, Any]
    allowed_tools: list[str]
    requires: list[str]


class Resolution(BaseModel):
    schema_version: Literal[1] = 1
    skills: list[Snapshot]
    auto_selection_strategy: Literal["manifest_rules", "manual"]


class ResolutionResult(BaseModel):
    schema_version: Literal[1] = 1
    data: Resolution
