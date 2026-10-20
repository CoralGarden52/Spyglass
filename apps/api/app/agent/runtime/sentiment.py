from collections import Counter
from typing import Any

SENTIMENTS = ("positive", "negative", "neutral", "mixed")


def aggregate_reviews(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unique = {row["fingerprint"]: row for row in rows}
    count = len(unique)
    overall = Counter(row["overall_sentiment"] for row in unique.values())
    aspects: dict[str, dict[str, int]] = {}
    for row in unique.values():
        seen = set()
        for aspect in row["aspects"]:
            marker = (aspect["aspect_key"], aspect["sentiment"], aspect.get("opinion_span", ""))
            if marker in seen:
                continue
            seen.add(marker)
            values = aspects.setdefault(
                aspect["aspect_key"], {**dict.fromkeys(SENTIMENTS, 0), "denominator": 0}
            )
            values[aspect["sentiment"]] += 1
            values["denominator"] += 1
    return {
        "sample_count": count,
        "overall": {
            s: {"count": overall[s], "ratio": overall[s] / count if count else None}
            for s in SENTIMENTS
        },
        "aspects": aspects,
        "platforms": sorted({str(r.get("source_platform", "unknown")) for r in unique.values()}),
        "bias_notice": (
            "仅代表可访问来源中的去重样本；公开评论存在平台、语言和自选择偏差，不代表全部用户。"
        ),
    }
