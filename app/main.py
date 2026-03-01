from collections import Counter
import random

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    CommentResult,
    SummaryResult,
)
from app.services.cache import get_cached_comment_pool, set_cached_comment_pool
from app.services.sentiment import analyze_comments, build_insight_summary
from app.services.youtube import extract_video_id, fetch_comments


MAX_CACHED_POOL_SIZE = 600


app = FastAPI(
    title="YouTube Sentiment API",
    version="0.1.0",
    description="Analyze YouTube comments for basic sentiment.",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

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


@app.get("/app")
def app_page():
    return FileResponse("static/index.html")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_video(payload: AnalyzeRequest) -> AnalyzeResponse:
    video_id = extract_video_id(str(payload.youtube_url))
    sample_size = payload.sample_size

    raw_pool = get_cached_comment_pool(video_id)

    if raw_pool is None:
        raw_pool = fetch_comments(video_id, max_comments=MAX_CACHED_POOL_SIZE)

        if not raw_pool:
            raise RuntimeError("No comments were returned for this video.")

        set_cached_comment_pool(video_id, raw_pool)

    if len(raw_pool) <= sample_size:
        sampled_comments = raw_pool
    else:
        sampled_comments = random.sample(raw_pool, sample_size)

    comments = analyze_comments(sampled_comments, batch_size=25)
    summary = build_summary(comments)
    insights = build_insight_summary(comments)

    return AnalyzeResponse(
        video_id=video_id,
        summary=summary,
        insights=insights,
        comments=comments,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)