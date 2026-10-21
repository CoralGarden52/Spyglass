from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.agent.agents.reporting import ReportingNodes
from app.agent.runtime.contracts import ReportDraft, ReportSection


async def test_writer_cannot_silently_omit_a_persisted_claim() -> None:
    keys = ["product_capability", "pricing_analysis", "user_sentiment", "swot_analysis"]
    claim_id = str(uuid4())
    store = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(request_json={})),
        artifacts=AsyncMock(return_value={key: SimpleNamespace(payload={}) for key in keys}),
        claims=AsyncMock(return_value=[{"id": claim_id, "skill_id": "product_capability"}]),
        save_report=AsyncMock(return_value=uuid4()),
    )
    context = SimpleNamespace(
        store=store,
        call=AsyncMock(
            return_value={
                "title": "Controlled report",
                "sections": [{"skill_id": key, "claim_ids": []} for key in keys],
            }
        ),
    )
    node = ReportingNodes(context, 2)
    node.build_draft = AsyncMock(
        return_value=ReportDraft(
            title="Fallback", status="partial", sections=[], limitations=[], sentiment_summary={}
        )
    )
    result = await node.writer({})
    assert result["writer_error"] == "schema_error:writer_references"
    assert node.build_draft.call_args.args == (None,)


async def test_outline_preserves_every_claim_through_server_mapping() -> None:
    keys = ["product_capability", "pricing_analysis", "user_sentiment", "swot_analysis"]
    ids = [str(uuid4()), str(uuid4())]
    store = SimpleNamespace(
        run=AsyncMock(
            return_value=SimpleNamespace(request_json={"user_message": "User named targets"})
        ),
        artifacts=AsyncMock(return_value={k: SimpleNamespace(payload={}) for k in keys}),
        claims=AsyncMock(return_value=[{"id": i, "skill_id": "product_capability"} for i in ids]),
        save_report=AsyncMock(return_value=uuid4()),
    )
    context = SimpleNamespace(
        store=store,
        call=AsyncMock(
            return_value={"title": "Outline report", "sections": [{"skill_id": k} for k in keys]}
        ),
    )
    node = ReportingNodes(context, 2)
    node.build_draft = AsyncMock(
        return_value=ReportDraft(
            title="Outline report",
            status="partial",
            sections=[],
            limitations=[],
            sentiment_summary={},
        )
    )
    result = await node.writer({})
    assert result["writer_error"] is None
    plan = node.build_draft.call_args.args[0]
    assert [str(i) for i in plan.sections[0].claim_ids] == ids
    assert all(s.claim_ids == [] for s in plan.sections[1:])
    assert "claims" not in context.call.call_args.args[2]


async def test_truncated_analysis_is_directed_back_to_analyst_even_when_model_review_passes() -> (
    None
):
    artifact = SimpleNamespace(
        status="insufficient_evidence",
        payload={"status": "insufficient_evidence", "limitations": ["model_output_truncated"]},
    )
    draft = ReportDraft(
        title="Controlled report",
        status="partial",
        limitations=[],
        sentiment_summary={},
        sections=[
            ReportSection(
                skill_id="product_capability",
                heading="Product",
                status="insufficient_evidence",
                claims=[],
                analysis=artifact.payload,
                limitations=["model_output_truncated"],
            )
        ],
    )
    store = SimpleNamespace(
        artifacts=AsyncMock(return_value={"product_capability": artifact}),
        evidence=AsyncMock(return_value=[]),
        claims=AsyncMock(return_value=[]),
        rows=AsyncMock(
            return_value=[SimpleNamespace(version=1, content_json=draft.model_dump(mode="json"))]
        ),
        review=AsyncMock(),
        save_report=AsyncMock(),
    )
    context = SimpleNamespace(
        store=store,
        call=AsyncMock(return_value={"passed": True, "issues": []}),
        definitions={"product_capability": {"kind": "core"}},
    )
    result = await ReportingNodes(context, 2).reviewer({})
    assert result["review_result"]["next_target"] == "analyst"
    assert result["review_result"]["status"] == "repair"
