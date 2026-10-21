from app.agent.runtime.evidence_context import evidence_context


def test_context_round_robins_requested_entities_without_changing_stored_text():
    rows = [
        {
            "id": str(i),
            "category": "product",
            "excerpt": "源" * 3000,
            "locator": {"competitor_name": "甲" if i < 70 else "乙"},
        }
        for i in range(75)
    ]
    result = evidence_context(rows, "analyst")
    assert len(result) == 32
    assert result[0]["id"] == "0" and result[1]["id"] == "70"
    assert all(len(row["excerpt"]) == 2000 and row["context_excerpt_truncated"] for row in result)
    assert all(len(row["excerpt"]) == 3000 for row in rows)


def test_normalizer_receives_only_profile_and_review_sources_with_exact_quote_prefixes():
    rows = [
        {"id": str(i), "category": kind, "excerpt": "Exact quote", "locator": {}}
        for i, kind in enumerate(["pricing", "review", "product", "market"])
    ]
    result = evidence_context(rows, "normalizer")
    assert {r["id"] for r in result} == {"1", "2"}
    assert all(r["excerpt"] == "Exact quote" and not r["context_excerpt_truncated"] for r in result)
