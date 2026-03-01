from dataclasses import dataclass
from threading import Lock
from time import time


CACHE_TTL_SECONDS = 15 * 60  # 15 minutes


@dataclass
class CachedCommentPool:
    comments: list[dict[str, str]]
    expires_at: float


_cache: dict[str, CachedCommentPool] = {}
_cache_lock = Lock()


def get_cached_comment_pool(video_id: str) -> list[dict[str, str]] | None:
    with _cache_lock:
        entry = _cache.get(video_id)

        if entry is None:
            return None

        if entry.expires_at <= time():
            _cache.pop(video_id, None)
            return None

        return list(entry.comments)


def set_cached_comment_pool(video_id: str, comments: list[dict[str, str]]) -> None:
    with _cache_lock:
        _cache[video_id] = CachedCommentPool(
            comments=list(comments),
            expires_at=time() + CACHE_TTL_SECONDS,
        )


def clear_cached_comment_pool(video_id: str) -> None:
    with _cache_lock:
        _cache.pop(video_id, None)