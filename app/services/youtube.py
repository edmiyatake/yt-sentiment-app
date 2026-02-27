import os
from urllib.parse import parse_qs, urlparse

import requests

YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def extract_video_id(youtube_url: str) -> str:
    """
    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    """
    parsed = urlparse(youtube_url)
    host = parsed.netloc.lower()

    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.lstrip("/").split("/")[0]
        if video_id:
            return video_id

    if "youtube.com" in host:
        query_params = parse_qs(parsed.query)

        if "v" in query_params and query_params["v"]:
            return query_params["v"][0]

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed"}:
            return path_parts[1]

    raise ValueError("Could not extract a valid YouTube video ID from that URL.")


def _youtube_get(endpoint: str, params: dict) -> dict:
    if not YOUTUBE_API_KEY:
        raise RuntimeError("Missing YOUTUBE_API_KEY environment variable.")

    url = f"{YOUTUBE_API_BASE_URL}/{endpoint}"
    full_params = {
        **params,
        "key": YOUTUBE_API_KEY,
    }

    response = requests.get(url, params=full_params, timeout=15)

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = response.text
        raise RuntimeError(f"YouTube API request failed: {error_payload}") from exc

    return response.json()


def fetch_comments(video_id: str, max_comments: int = 100) -> list[dict[str, str]]:
    """
    Fetch top-level comments for a video.

    Returns raw comments only.
    Sentiment labeling stays in sentiment.py.
    """
    comments: list[dict[str, str]] = []
    page_token: str | None = None

    while len(comments) < max_comments:
        remaining = max_comments - len(comments)
        batch_size = min(100, remaining)

        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": batch_size,
            "textFormat": "plainText",
            "order": "time",
        }

        if page_token:
            params["pageToken"] = page_token

        data = _youtube_get("commentThreads", params)

        for item in data.get("items", []):
            top_comment = item["snippet"]["topLevelComment"]["snippet"]
            comments.append(
                {
                    "author": top_comment.get("authorDisplayName", "Unknown"),
                    "text": top_comment.get("textDisplay", ""),
                }
            )

            if len(comments) >= max_comments:
                break

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return comments