import json
import re
from collections import Counter, defaultdict
from typing import Any, Literal

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


class BatchCommentInsight(BaseModel):
    index: int
    sentiment: SentimentLabel
    reason: str
    theme: str
    theme_detail: str


class BatchCommentInsightResponse(BaseModel):
    items: list[BatchCommentInsight]


def _get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")
    return OpenAI(api_key=settings.openai_api_key)


def _normalize_category(value: str, fallback: str = "general_feedback", max_length: int = 40) -> str:
    cleaned = value.strip().lower()
    cleaned = cleaned.replace("&", " and ")
    cleaned = re.sub(r"[^a-z0-9\s_-]", "", cleaned)
    cleaned = re.sub(r"[\s-]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")

    if not cleaned:
        return fallback

    return cleaned[:max_length]


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
            theme="general_feedback",
            theme_detail="general feedback",
        )
        for i in range(batch_size)
    ]


def _build_prompt_context(
    company_name: str | None = None,
    video_title: str | None = None,
    video_context: str | None = None,
) -> str:
    parts: list[str] = []

    if company_name:
        parts.append(f"Company: {company_name}")
    if video_title:
        parts.append(f"Video title: {video_title}")
    if video_context:
        parts.append(f"Video context: {video_context}")

    if not parts:
        return "No extra company or video context was provided."

    return "\n".join(parts)


def _classify_batch(
    raw_comments: list[dict[str, str]],
    company_name: str | None = None,
    video_title: str | None = None,
    video_context: str | None = None,
) -> list[BatchCommentInsight]:
    client = _get_client()

    payload = [
        {
            "index": index,
            "text": comment.get("text", ""),
        }
        for index, comment in enumerate(raw_comments)
    ]

    prompt_context = _build_prompt_context(
        company_name=company_name,
        video_title=video_title,
        video_context=video_context,
    )

    response = client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {
                "role": "system",
                "content": (
                    "You analyze YouTube comments and reviews about a company's video.\n"
                    "For each comment, return:\n"
                    "- index\n"
                    "- sentiment: exactly one of positive, neutral, or negative\n"
                    "- reason: one short sentence explaining the label\n"
                    "- theme: a short reusable category that YOU generate yourself in snake_case\n"
                    "- theme_detail: a short specific subtopic in 1 to 4 words\n\n"
                    "Rules:\n"
                    "- Positive = praise, approval, trust, excitement, or satisfaction.\n"
                    "- Negative = complaint, frustration, criticism, disappointment, or distrust.\n"
                    "- Neutral = factual, mixed, unclear, or neither clearly positive nor negative.\n"
                    "- Reuse the same theme names when meanings overlap.\n"
                    "- Do not invent near-duplicate categories.\n"
                    "- Prefer broad, stable categories such as product_quality, pricing, "
                    "customer_service, delivery, trust, communication, brand_perception, "
                    "video_quality, feature_request, or usability when appropriate.\n"
                    "- theme should usually be 1 to 3 words in snake_case.\n"
                    "- theme_detail should be concise and reusable.\n"
                    "- If unclear, use theme 'general_feedback' and detail 'general feedback'.\n"
                    "- Consider nuance, sarcasm, and context where possible."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Analyze this JSON array of YouTube comments about a company video.\n\n"
                    f"{prompt_context}\n\n"
                    "Classify each comment so the results can later be aggregated into:\n"
                    "- overall dominant sentiment\n"
                    "- percentage breakdown of positive, neutral, and negative\n"
                    "- recurring themes across comments\n\n"
                    "Comments JSON:\n"
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
                    theme="general_feedback",
                    theme_detail="general feedback",
                )
            )
            continue

        ordered_results.append(
            BatchCommentInsight(
                index=index,
                sentiment=item.sentiment,
                reason=_normalize_reason(item.reason),
                theme=_normalize_category(item.theme, fallback="general_feedback", max_length=40),
                theme_detail=_normalize_text(
                    item.theme_detail,
                    fallback="general feedback",
                    max_length=50,
                ),
            )
        )

    return ordered_results


def analyze_comments(
    raw_comments: list[dict[str, str]],
    batch_size: int = 25,
    company_name: str | None = None,
    video_title: str | None = None,
    video_context: str | None = None,
) -> list[CommentResult]:
    results: list[CommentResult] = []

    for start in range(0, len(raw_comments), batch_size):
        batch = raw_comments[start:start + batch_size]
        insights = _classify_batch(
            batch,
            company_name=company_name,
            video_title=video_title,
            video_context=video_context,
        )

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

        theme = _normalize_category(getattr(comment, "theme", "") or "general_feedback")
        detail = _normalize_text(
            getattr(comment, "theme_detail", "") or "general feedback",
            fallback="general feedback",
            max_length=50,
        )

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


def build_summary_report(
    comments: list[CommentResult],
    top_n: int = 5,
    top_detail_n: int = 3,
) -> dict[str, Any]:
    total = len(comments)

    if total == 0:
        return {
            "sentiment_summary": "No comments available.",
            "dominant_sentiment": "neutral",
            "percentage_breakdown": {
                "positive": 0.0,
                "neutral": 0.0,
                "negative": 0.0,
            },
            "main_recurring_themes": [],
        }

    sentiment_counts = Counter(comment.sentiment for comment in comments)

    percentages = {
        "positive": round(sentiment_counts.get("positive", 0) / total * 100, 1),
        "neutral": round(sentiment_counts.get("neutral", 0) / total * 100, 1),
        "negative": round(sentiment_counts.get("negative", 0) / total * 100, 1),
    }

    most_common = sentiment_counts.most_common()
    top_count = most_common[0][1]
    dominant_labels = [label for label, count in most_common if count == top_count]

    if len(dominant_labels) == 1:
        dominant_sentiment = dominant_labels[0]
        sentiment_summary = f"Overall sentiment is mostly {dominant_sentiment}."
    else:
        dominant_sentiment = "mixed"
        sentiment_summary = "Overall sentiment is mixed with no single dominant sentiment."

    theme_counts = Counter()
    theme_details: dict[str, Counter] = defaultdict(Counter)
    theme_sentiments: dict[str, Counter] = defaultdict(Counter)

    for comment in comments:
        theme = _normalize_category(getattr(comment, "theme", "") or "general_feedback")
        detail = _normalize_text(
            getattr(comment, "theme_detail", "") or "general feedback",
            fallback="general feedback",
            max_length=50,
        )

        theme_counts[theme] += 1
        theme_details[theme][detail] += 1
        theme_sentiments[theme][comment.sentiment] += 1

    main_recurring_themes: list[dict[str, Any]] = []

    for theme, count in theme_counts.most_common(top_n):
        keywords = [
            detail
            for detail, _detail_count in theme_details[theme].most_common(top_detail_n)
        ]

        main_recurring_themes.append(
            {
                "theme": theme,
                "count": count,
                "keywords": keywords,
                "sentiment_breakdown": {
                    "positive": theme_sentiments[theme].get("positive", 0),
                    "neutral": theme_sentiments[theme].get("neutral", 0),
                    "negative": theme_sentiments[theme].get("negative", 0),
                },
            }
        )

    return {
        "sentiment_summary": sentiment_summary,
        "dominant_sentiment": dominant_sentiment,
        "percentage_breakdown": percentages,
        "main_recurring_themes": main_recurring_themes,
    }


def format_summary_report(report: dict[str, Any]) -> str:
    lines = [
        "Sentiment Summary Report",
        f"- Sentiment summary: {report['sentiment_summary']}",
        "- Percentage breakdown:",
        f"  - Positive: {report['percentage_breakdown']['positive']}%",
        f"  - Neutral: {report['percentage_breakdown']['neutral']}%",
        f"  - Negative: {report['percentage_breakdown']['negative']}%",
        "- Main recurring themes:",
    ]

    themes = report.get("main_recurring_themes", [])
    if not themes:
        lines.append("  - No recurring themes detected.")
        return "\n".join(lines)

    for item in themes:
        keywords = ", ".join(item.get("keywords", [])) or "general feedback"
        sentiment_breakdown = item.get("sentiment_breakdown", {})
        lines.append(
            "  - "
            f"{item['theme']} ({item['count']} mentions): "
            f"{keywords} | "
            f"+{sentiment_breakdown.get('positive', 0)} / "
            f"={sentiment_breakdown.get('neutral', 0)} / "
            f"-{sentiment_breakdown.get('negative', 0)}"
        )

    return "\n".join(lines)