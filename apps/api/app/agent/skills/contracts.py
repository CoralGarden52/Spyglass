from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.schemas import Mode


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScenarioConfig(Contract):
    source_language: Literal["auto", "zh", "en"] = "auto"


class AnalysisConfig(Contract):
    max_findings: int = Field(default=10, ge=3, le=30)
    evidence_quote_limit: int = Field(default=5, ge=1, le=10)


class SentimentConfig(AnalysisConfig):
    review_sample_limit: int = Field(default=100, ge=1, le=500)
    minimum_sample_warning: int = Field(default=20, ge=1, le=100)


class ScenarioInput(Contract):
    user_request: str = Field(min_length=1, max_length=8000)
    competitor_names: list[str] = Field(max_length=10)
    mode: Mode = "standard"


class ScenarioContext(Contract):
    dimensions: list[str] = Field(min_length=1)
    source_priorities: list[str] = Field(min_length=1)
    review_aspects: list[str] = Field(min_length=1)


class EvidenceInput(Contract):
    user_request: str = Field(min_length=1, max_length=8000)
    competitor_ids: list[UUID] = Field(max_length=10)
    evidence_ids: list[UUID]
    scenario_context: ScenarioContext


class DependentAnalysisInput(EvidenceInput):
    analysis_refs: dict[str, UUID] = Field(min_length=1)


class Finding(Contract):
    statement: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[UUID]
    evidence_status: Literal["supported", "partial", "insufficient_evidence"]

    @model_validator(mode="after")
    def require_support(self) -> "Finding":
        if self.evidence_status == "supported" and not self.evidence_ids:
            raise ValueError("Supported findings require evidence")
        return self


class AnalysisResult(Contract):
    schema_version: Literal[1] = 1
    status: Literal["complete", "partial", "insufficient_evidence"]
    limitations: list[str]


class FeatureFact(Finding):
    feature_name: str
    feature_status: Literal["supported", "partial", "not_found", "unsupported", "unverified"]


class ProductResult(AnalysisResult):
    positioning: list[Finding]
    features: list[FeatureFact]


class PricePlan(Finding):
    plan_name: str
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    billing_unit: str | None = None
    observed_at: datetime

    @model_validator(mode="after")
    def require_price_units(self) -> "PricePlan":
        if self.amount is not None and (not self.currency or not self.billing_unit):
            raise ValueError("Known prices require currency and billing unit")
        return self


class PricingResult(AnalysisResult):
    plans: list[PricePlan]


class ReviewAspect(Contract):
    aspect_key: str
    opinion_span: str
    sentiment: Literal["positive", "negative", "neutral", "mixed"]
    evidence_id: UUID


class ReviewObservation(Contract):
    evidence_id: UUID
    source_platform: str
    fingerprint: str
    overall_sentiment: Literal["positive", "negative", "neutral", "mixed"]
    aspects: list[ReviewAspect]


class SentimentResult(AnalysisResult):
    reviews: list[ReviewObservation]
    sampling_bias: list[str] = Field(min_length=1)


class SWOTResult(AnalysisResult):
    strengths: list[Finding]
    weaknesses: list[Finding]
    opportunities: list[Finding]
    threats: list[Finding]


class MarketResult(AnalysisResult):
    participants: list[Finding]
    positioning_differences: list[Finding]


class BusinessResult(AnalysisResult):
    revenue_paths: list[Finding]
    channels_and_costs: list[Finding]


class StrategyResult(AnalysisResult):
    opportunities: list[Finding]
    risks: list[Finding]
    recommendations: list[Finding]


SCHEMAS: dict[str, type[BaseModel]] = {
    cls.__name__: cls
    for cls in (
        ScenarioConfig,
        AnalysisConfig,
        SentimentConfig,
        ScenarioInput,
        ScenarioContext,
        EvidenceInput,
        DependentAnalysisInput,
        ProductResult,
        PricingResult,
        SentimentResult,
        SWOTResult,
        MarketResult,
        BusinessResult,
        StrategyResult,
    )
}


def schema_document(name: str) -> dict[str, Any]:
    return SCHEMAS[name].model_json_schema()
