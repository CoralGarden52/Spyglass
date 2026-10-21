"""Bounded public search coverage, independent of model ordering and availability."""

import re
from datetime import date, timedelta
from typing import Literal

from app.agent.runtime.contracts import CollectionPlan, SearchTask

CORE_CATEGORIES: tuple[Literal["product", "pricing", "review"], ...] = (
    "product",
    "pricing",
    "review",
)


def default_query(
    name: str, category: str, scenario: str, as_of: date, *, broad: bool = False
) -> str:
    identity = "AI software" if scenario == "ai_llm" else "product"
    terms = {
        "product": "official features documentation",
        "pricing": "official pricing plans billing",
        "review": "user reviews feedback after:" + (as_of - timedelta(days=365)).isoformat(),
        "market": "market competitors news after:" + (as_of - timedelta(days=365)).isoformat(),
    }
    if broad:
        terms = {
            "product": "功能 文档",
            "pricing": "pricing 价格 套餐",
            "review": "用户 评价 使用体验",
            "market": "市场 竞品 动态",
        }
    tail = " " + identity + " " + terms[category]
    # Reserve the semantic suffix rather than truncating away the category/date.
    label = " ".join(name.replace('"', " ").split())[: 126 - len(tail)]
    return '"' + label + '"' + tail


def coverage_searches(
    names: list[str], collection: CollectionPlan | None, mode: str, scenario: str, as_of: date
) -> list[SearchTask]:
    candidates: list[SearchTask] = []
    for task in collection.searches if collection else []:
        # No authoritative official-domain map exists at this stage. Do not execute
        # model-invented site restrictions; discovery queries find public official pages.
        if re.search(r"\bsite\s*:", task.query, re.IGNORECASE):
            continue
        matched = [
            n
            for n in names
            if re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", task.query, re.IGNORECASE)
        ]
        if len(matched) == 1:
            query = " ".join(task.query.split())
            if scenario == "ai_llm" and "ai software" not in query.casefold():
                query += " AI software"
            if task.category in {"review", "market"}:
                query = re.sub(r"\bafter\s*:\S+", "", query, flags=re.IGNORECASE).strip()
                query += " after:" + (as_of - timedelta(days=365)).isoformat()
            if len(query) > 128:
                query = default_query(matched[0], task.category, scenario, as_of)
            candidates.append(
                task.model_copy(update={"query": query, "competitor_name": matched[0]})
            )
    selected: list[SearchTask] = []
    used: set[str] = set()
    for category in CORE_CATEGORIES:
        for name in names:
            candidate = next(
                (t for t in candidates if t.category == category and t.competitor_name == name),
                None,
            )
            task = candidate or SearchTask(
                query=default_query(name, category, scenario, as_of),
                category=category,
                competitor_name=name,
            )
            selected.append(task)
            used.add(task.query.casefold())
    limit = min(40, len(selected) + {"quick": 0, "standard": 3, "deep": 10}.get(mode, 3))
    for task in candidates:
        if len(selected) >= limit:
            break
        if task.query.casefold() not in used:
            selected.append(task)
            used.add(task.query.casefold())
    return selected


def rewrite_empty_query(task: SearchTask, scenario: str, as_of: date) -> str | None:
    if not task.competitor_name:
        return None
    query = default_query(task.competitor_name, task.category, scenario, as_of, broad=True)
    return query if query.casefold() != task.query.casefold() else None
