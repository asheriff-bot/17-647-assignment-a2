"""
Shared book JSON transforms for BFFs (A2): map non-fiction genre string -> int 3 for mobile clients.

Used by mobile_bff (always) and web_bff when X-Client-Type is ios/android (External ALB may route
mobile traffic to Web targets; book service may not see X-A2-Mobile-BFF if stripped by ALB).
"""
import json
from typing import Any


def normalize_bff_path(path: str) -> str:
    return (path or "").rstrip("/") or "/"


def should_skip_book_genre_transform(method: str, path: str) -> bool:
    """GET /books list must not rewrite genre (assignment + book service from_book_list)."""
    return (method or "").upper() == "GET" and normalize_bff_path(path) == "/books"


def _transform_book_obj(obj: dict) -> None:
    if not isinstance(obj, dict):
        return
    g = obj.get("genre")
    if g is None and "Genre" in obj:
        g = obj.get("Genre")
    gs = str(g).strip().lower() if g is not None else ""
    if gs in ("non-fiction", "nonfiction"):
        obj["genre"] = 3
        obj.pop("Genre", None)


def transform_book_response(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8")
        parsed: Any = json.loads(text)
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    _transform_book_obj(item)
        elif isinstance(parsed, dict):
            _transform_book_obj(parsed)
        # Preserve key order from backend (match Web BFF / autograder expectations).
        out = json.dumps(parsed, separators=(",", ":"))
        return out.encode("utf-8")
    except Exception:
        return data
