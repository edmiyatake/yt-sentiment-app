from typing import Literal

from pydantic import BaseModel, HttpUrl


class AnalyzeRequest(BaseModel):
    youtube_url: HttpUrl
    sample_size: Literal[50, 100, 200] = 50


class CommentResult(BaseModel):
    author: str
    text: str
    sentiment: Literal["positive", "neutral", "negative"]
    reason: str
    theme: str
    theme_detail: str


class SummaryResult(BaseModel):
    positive: int
    neutral: int
    negative: int


class ThemeDetailResult(BaseModel):
    detail: str
    count: int


class ThemeResult(BaseModel):
    theme: str
    count: int
    details: list[ThemeDetailResult]


class InsightSummary(BaseModel):
    positive_themes: list[ThemeResult]
    negative_themes: list[ThemeResult]
    neutral_themes: list[ThemeResult]


class AnalyzeResponse(BaseModel):
    video_id: str
    summary: SummaryResult
    insights: InsightSummary
    comments: list[CommentResult]