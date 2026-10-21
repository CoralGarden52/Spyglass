"""Bound model input text while keeping every selected value traceable to stored evidence."""

from collections import defaultdict, deque
from typing import Any


def evidence_context(rows: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], deque[dict[str, Any]]] = defaultdict(deque)
    for row in rows:
        category = str(row.get("category", ""))
        if role == "normalizer" and category not in {"review", "product"}:
            continue
        name = str((row.get("locator") or {}).get("competitor_name") or "")
        groups[(name, category)].append(row)
    result: list[dict[str, Any]] = []
    limit = max(len(groups), 24 if role == "normalizer" else 32)
    while len(result) < limit and any(groups.values()):
        for group in groups.values():
            if not group or len(result) >= limit:
                continue
            row = group.popleft()
            text = str(row.get("excerpt", ""))
            result.append(
                {**row, "excerpt": text[:2000], "context_excerpt_truncated": len(text) > 2000}
            )
    return result
