from collections import Counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    CommentResult,
    SummaryResult,
)
from app.services.sentiment import analyze_comments
from app.services.youtube import extract_video_id, fetch_comments


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


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=502,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
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
    raw_comments = fetch_comments(video_id, max_comments=50)
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