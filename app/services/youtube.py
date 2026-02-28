from urllib.parse import parse_qs, urlparse

import requests

from app.core.config import settings

YOUTUBE_API_BASE_URL = settings.youtube_api_base_url


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


def _parse_error_payload(response: requests.Response) -> tuple[str | None, str | None]:
    """
    Pull the first Google API error reason + message from the response body.
    """
    try:
        payload = response.json()
    except ValueError:
        return None, None

    error_obj = payload.get("error", {})
    errors = error_obj.get("errors", [])

    reason = None
    if isinstance(errors, list) and errors:
        reason = errors[0].get("reason")

    message = error_obj.get("message")
    return reason, message


def _raise_friendly_api_error(response: requests.Response) -> None:
    reason, message = _parse_error_payload(response)

    if reason == "commentsDisabled":
        raise RuntimeError("Comments are disabled for this video.")

    if reason == "videoNotFound":
        raise RuntimeError("Video not found. Check that the YouTube URL is valid and public.")

    if reason == "quotaExceeded":
        raise RuntimeError("YouTube API quota exceeded. Try again later or use a different API key.")

    if reason == "forbidden":
        raise RuntimeError(
            "YouTube denied access to this request. Check that your API key is valid and that the YouTube Data API is enabled."
        )

    if reason == "invalidPageToken":
        raise RuntimeError("YouTube rejected the page token. Please retry the request.")

    if message:
        raise RuntimeError(f"YouTube API error: {message}")

    raise RuntimeError(f"YouTube API request failed with status {response.status_code}.")


def _youtube_get(endpoint: str, params: dict) -> dict:
    if not settings.youtube_api_key:
        raise RuntimeError("Missing YOUTUBE_API_KEY environment variable.")

    url = f"{YOUTUBE_API_BASE_URL}/{endpoint}"
    full_params = {
        **params,
        "key": settings.youtube_api_key,
    }

    try:
        response = requests.get(url, params=full_params, timeout=15)
    except requests.RequestException as exc:
        raise RuntimeError("Could not reach the YouTube API.") from exc

    if not response.ok:
        _raise_friendly_api_error(response)

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("YouTube API returned an unreadable response.") from exc


def fetch_comments(video_id: str, max_comments: int = 100) -> list[dict[str, str]]:
    """
    Fetch top-level comments for a video.
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