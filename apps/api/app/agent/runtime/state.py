from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    tenant_id: str
    user_id: str
    project_id: str
    thread_id: str
    run_id: str
    plan_id: str | None
    evidence_ids: list[str]
    profile_ids: list[str]
    product_ref: str | None
    pricing_ref: str | None
    sentiment_ref: str | None
    analysis_refs: dict[str, str]
    report_draft_id: str | None
    review_result: dict[str, Any] | None
    review_count: int
    status: str
    repair_changed: bool
    writer_error: str | None
