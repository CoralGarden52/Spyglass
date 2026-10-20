from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, Field, computed_field, field_validator


class SearchResultMetadata(BaseModel):
    """Native provider values; the confidence index is not a truth probability."""

    title: str
    url: str
    snippet: str = ""
    summary: str = ""
    content: str = ""
    rerank_score: float | None = Field(default=None, ge=0, le=3, allow_inf_nan=False)
    authority: int = Field(default=-1, ge=-1, le=4)
    date: AwareDatetime | None = None
    site_name: str | None = None
    site_icon: str | None = None

    @field_validator("date")
    @classmethod
    def utc_date(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def source_confidence(self) -> float | None:
        if self.rerank_score is None or self.authority == -1:
            return None
        return round(0.7 * self.rerank_score / 3 + 0.3 * self.authority / 4, 4)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def confidence_policy(self) -> str:
        return "deepseek-native-weighted-v1"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def high_quality(self) -> bool:
        return self.rerank_score is not None and self.rerank_score >= 1.5

    @computed_field  # type: ignore[prop-decorator]
    @property
    def high_authority(self) -> bool:
        return self.authority >= 3


class SearchSourceView(BaseModel):
    evidence_id: str
    validity_status: str
    result: SearchResultMetadata
