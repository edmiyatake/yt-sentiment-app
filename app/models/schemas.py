from typing import Literal

from pydantic import BaseModel, HttpUrl


class AnalyzeRequest(BaseModel):
    youtube_url: HttpUrl
    sample_size: Literal[50, 100, 200] = 50


class CommentResult(BaseModel):
    author: str
    text: str
    sentiment: Literal["positive", "neutral", "negative"]


class SummaryResult(BaseModel):
    positive: int
    neutral: int
    negative: int


class AnalyzeResponse(BaseModel):
    video_id: str
    summary: SummaryResult
    comments: list[CommentResult]