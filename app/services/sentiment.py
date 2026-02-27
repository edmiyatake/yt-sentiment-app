import re
from typing import Literal

from app.models.schemas import CommentResult

SentimentLabel = Literal["positive", "neutral", "negative"]

POSITIVE_WORDS = {
    "good",
    "great",
    "love",
    "awesome",
    "amazing",
    "helpful",
    "nice",
    "excellent",
    "fun",
    "best",
}

NEGATIVE_WORDS = {
    "bad",
    "terrible",
    "hate",
    "awful",
    "worst",
    "boring",
    "annoying",
    "useless",
    "stupid",
    "confusing",
}


def classify_sentiment(text: str) -> SentimentLabel:
    words = re.findall(r"\b[a-z]+\b", text.lower())

    positive_count = sum(1 for word in words if word in POSITIVE_WORDS)
    negative_count = sum(1 for word in words if word in NEGATIVE_WORDS)

    if positive_count > negative_count:
        return "positive"
    if negative_count > positive_count:
        return "negative"
    return "neutral"


def analyze_comments(raw_comments: list[dict[str, str]]) -> list[CommentResult]:
    results: list[CommentResult] = []

    for comment in raw_comments:
        text = comment.get("text", "")
        results.append(
            CommentResult(
                author=comment.get("author", "Unknown"),
                text=text,
                sentiment=classify_sentiment(text),
            )
        )

    return results