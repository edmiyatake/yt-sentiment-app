import json
import re
from collections import Counter, defaultdict
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.models.schemas import (
    CommentResult,
    InsightSummary,
    ThemeDetailResult,
    ThemeResult,
)

SentimentLabel = Literal["positive", "neutral", "negative"]
ThemeLabel = Literal[
    "creativity",
    "gameplay",
    "difficulty",
    "visuals",
    "audio",
    "story",
    "ui_ux",
    "performance",
    "balance",
    "bugs",
    "immersion",
    "other",
]


class BatchCommentInsight(BaseModel):
    index: int
    sentiment: SentimentLabel
    reason: str
    theme: ThemeLabel
    theme_detail: str


class BatchCommentInsightResponse(BaseModel):
    items: list[BatchCommentInsight]


def _get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")
    return OpenAI(api_key=settings.openai_api_key)


def _normalize_text(value: str, fallback: str, max_length: int = 60) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\s-]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return fallback

    return cleaned[:max_length]


def _normalize_reason(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "No explanation available."
    return cleaned[:220]


def _default_batch_result(batch_size: int) -> list[BatchCommentInsight]:
    return [
        BatchCommentInsight(
            index=i,
            sentiment="neutral",
            reason="No explanation available.",
            theme="other",
            theme_detail="general feedback",
        )
        for i in range(batch_size)
    ]


def _classify_batch(raw_comments: list[dict[str, str]]) -> list[BatchCommentInsight]:
    client = _get_client()

    payload = [
        {
            "index": index,
            "text": comment.get("text", ""),
        }
        for index, comment in enumerate(raw_comments)
    ]

    response = client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {
                "role": "system",
                "content": (
                    "You analyze YouTube comments about a video game.\n"
                    "For each comment, return:\n"
                    "- index\n"
                    "- sentiment: positive, neutral, or negative\n"
                    "- reason: one short sentence explaining the label\n"
                    "- theme: exactly one of these values: "
                    "creativity, gameplay, difficulty, visuals, audio, story, "
                    "ui_ux, performance, balance, bugs, immersion, other\n"
                    "- theme_detail: a specific part inside that theme, in 1 to 3 words\n\n"
                    "Important:\n"
                    "- If theme is creativity, theme_detail should identify WHAT part feels creative.\n"
                    "- Good creativity details include: game mechanics, level design, world design, "
                    "puzzle design, enemy design, art direction, story concepts.\n"
                    "- Use concise reusable labels.\n"
                    "- If unclear, use theme 'other' and detail 'general feedback'."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Analyze this JSON array of game-related YouTube comments:\n"
                    f"{json.dumps(payload, ensure_ascii=False)}"
                ),
            },
        ],
        text_format=BatchCommentInsightResponse,
    )

    parsed = response.output_parsed
    if parsed is None:
        return _default_batch_result(len(raw_comments))

    items_by_index = {item.index: item for item in parsed.items}
    ordered_results: list[BatchCommentInsight] = []

    for index in range(len(raw_comments)):
        item = items_by_index.get(index)

        if item is None:
            ordered_results.append(
                BatchCommentInsight(
                    index=index,
                    sentiment="neutral",
                    reason="No explanation available.",
                    theme="other",
                    theme_detail="general feedback",
                )
            )
            continue

        ordered_results.append(
            BatchCommentInsight(
                index=index,
                sentiment=item.sentiment,
                reason=_normalize_reason(item.reason),
                theme=item.theme,
                theme_detail=_normalize_text(
                    item.theme_detail,
                    fallback="general feedback",
                    max_length=40,
                ),
            )
        )

    return ordered_results


def analyze_comments(
    raw_comments: list[dict[str, str]],
    batch_size: int = 25,
) -> list[CommentResult]:
    results: list[CommentResult] = []

    for start in range(0, len(raw_comments), batch_size):
        batch = raw_comments[start:start + batch_size]
        insights = _classify_batch(batch)

        for comment, insight in zip(batch, insights):
            results.append(
                CommentResult(
                    author=comment.get("author", "Unknown"),
                    text=comment.get("text", ""),
                    sentiment=insight.sentiment,
                    reason=insight.reason,
                    theme=insight.theme,
                    theme_detail=insight.theme_detail,
                )
            )

    return results


def _build_theme_groups(
    comments: list[CommentResult],
    sentiment: SentimentLabel,
    top_n: int = 5,
    top_detail_n: int = 3,
) -> list[ThemeResult]:
    theme_counts = Counter()
    detail_counts: dict[str, Counter] = defaultdict(Counter)

    for comment in comments:
        if comment.sentiment != sentiment:
            continue

        theme = comment.theme or "other"
        detail = comment.theme_detail or "general feedback"

        theme_counts[theme] += 1
        detail_counts[theme][detail] += 1

    groups: list[ThemeResult] = []

    for theme, count in theme_counts.most_common(top_n):
        details = [
            ThemeDetailResult(detail=detail, count=detail_count)
            for detail, detail_count in detail_counts[theme].most_common(top_detail_n)
        ]

        groups.append(
            ThemeResult(
                theme=theme,
                count=count,
                details=details,
            )
        )

    return groups


def build_insight_summary(
    comments: list[CommentResult],
    top_n: int = 5,
    top_detail_n: int = 3,
) -> InsightSummary:
    return InsightSummary(
        positive_themes=_build_theme_groups(comments, "positive", top_n, top_detail_n),
        negative_themes=_build_theme_groups(comments, "negative", top_n, top_detail_n),
        neutral_themes=_build_theme_groups(comments, "neutral", top_n, top_detail_n),
    )