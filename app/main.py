from collections import Counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    CommentResult,
    SummaryResult,
)
from app.services.sentiment import analyze_comments
from app.services.youtube import extract_video_id, mock_fetch_comments


app = FastAPI(
    title="YouTube Sentiment API",
    version="0.1.0",
    description="Analyze YouTube comments for basic sentiment."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_summary(comments: list[CommentResult]) -> SummaryResult:
    counts = Counter(comment.sentiment for comment in comments)
    return SummaryResult(
        positive=counts.get("positive", 0),
        neutral=counts.get("neutral", 0),
        negative=counts.get("negative", 0),
    )


@app.get("/")
def root() -> dict:
    return {
        "message": "YouTube Sentiment API is running.",
        "docs_url": "/docs",
    }


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_video(payload: AnalyzeRequest) -> AnalyzeResponse:
    video_id = extract_video_id(str(payload.youtube_url))
    raw_comments = mock_fetch_comments(video_id)
    comments = analyze_comments(raw_comments)
    summary = build_summary(comments)

    return AnalyzeResponse(
        video_id=video_id,
        summary=summary,
        comments=comments,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)