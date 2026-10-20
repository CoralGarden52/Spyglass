from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import Field

from app.agent.skills.contracts import Contract

Role = Literal["planner", "collector", "normalizer", "analyst", "writer", "reviewer"]
Target = Literal["collector", "analyst", "writer"]


class ModelInput(Contract):
    role: Role
    prompt_version: str = "research-v1"
    instructions: str
    context: dict[str, Any]
    output_schema: dict[str, Any]
    max_tokens: int = Field(default=3000, ge=100, le=12000)


class ModelReply(Contract):
    data: dict[str, Any]
    model: str
    usage: dict[str, int] | None = None


class ModelProvider(Protocol):
    async def generate(self, call: ModelInput) -> ModelReply: ...


class ResearchPlan(Contract):
    competitor_names: list[str] = Field(min_length=1, max_length=10)
    scope: str = Field(min_length=1, max_length=2000)


class SearchTask(Contract):
    query: str = Field(min_length=1, max_length=128, pattern=r"\S")
    category: Literal["product", "pricing", "review", "market"]


class CollectionPlan(Contract):
    searches: list[SearchTask] = Field(min_length=1, max_length=12)


class ProfileDraft(Contract):
    name: str = Field(min_length=1, max_length=200)
    evidence_ids: list[UUID]
    # Unknown websites must remain null; do not infer from product names.
    website: str | None = None


class ReviewDraft(Contract):
    competitor_name: str
    evidence_id: UUID
    quote: str = Field(min_length=5, max_length=2000)
    source_platform: str
    published_at: datetime | None = None
    language: str = "unknown"


class NormalizedBundle(Contract):
    profiles: list[ProfileDraft]
    reviews: list[ReviewDraft]
    limitations: list[str]


class Issue(Contract):
    type: Literal[
        "missing_evidence", "unsupported_claim", "contradiction", "schema_error", "outdated_source"
    ]
    severity: Literal["error", "warning"] = "error"
    target: Target
    skill_id: str | None = None
    claim_id: UUID | None = None
    evidence_id: UUID | None = None
    description: str = Field(min_length=1, max_length=1000)
    repair_request: str = Field(min_length=1, max_length=1000)


class ReviewVerdict(Contract):
    passed: bool
    issues: list[Issue]


class ReviewResult(ReviewVerdict):
    schema_version: Literal[1] = 1
    next_target: Target | None
    review_count: int
    status: Literal["passed", "repair", "needs_review"]
    before_digest: str


class SectionPlan(Contract):
    skill_id: str
    claim_ids: list[UUID]


class WritingPlan(Contract):
    title: str = Field(min_length=1, max_length=200)
    sections: list[SectionPlan] = Field(min_length=4, max_length=7)


class ReportClaim(Contract):
    id: UUID
    statement: str
    status: str
    evidence_ids: list[UUID]


class ReportSection(Contract):
    skill_id: str
    heading: str
    status: str
    claims: list[ReportClaim]
    analysis: dict[str, Any]
    limitations: list[str]


class ReportDraft(Contract):
    schema_version: Literal[1] = 1
    title: str
    status: Literal["partial", "complete", "needs_review"]
    sections: list[ReportSection]
    limitations: list[str]
    sentiment_summary: dict[str, Any]
