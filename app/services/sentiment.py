import json
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.models.schemas import CommentResult

SentimentLabel = Literal["positive", "neutral", "negative"]


class BatchSentimentItem(BaseModel):
    index: int
    sentiment: SentimentLabel


class BatchSentimentResponse(BaseModel):
    items: list[BatchSentimentItem]


def _get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")
    return OpenAI(api_key=settings.openai_api_key)


def _classify_batch(raw_comments: list[dict[str, str]]) -> list[SentimentLabel]:
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
                    "You are a sentiment classifier for YouTube comments. "
                    "For each input item, assign exactly one label: "
                    "positive, neutral, or negative. "
                    "Return one result for every index."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Classify the sentiment of this JSON array of comments:\n"
                    f"{json.dumps(payload, ensure_ascii=False)}"
                ),
            },
        ],
        text_format=BatchSentimentResponse,
    )

    parsed = response.output_parsed
    labels_by_index = {item.index: item.sentiment for item in parsed.items}

    labels: list[SentimentLabel] = []
    for index in range(len(raw_comments)):
        labels.append(labels_by_index.get(index, "neutral"))

    return labels


def analyze_comments(raw_comments: list[dict[str, str]], batch_size: int = 25) -> list[CommentResult]:
    results: list[CommentResult] = []

    for start in range(0, len(raw_comments), batch_size):
        batch = raw_comments[start:start + batch_size]
        labels = _classify_batch(batch)

        for comment, sentiment in zip(batch, labels):
            results.append(
                CommentResult(
                    author=comment.get("author", "Unknown"),
                    text=comment.get("text", ""),
                    sentiment=sentiment,
                )
            )

    return results