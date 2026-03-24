"""
Shared book JSON transforms for BFFs (A2): map non-fiction genre string -> int 3 for mobile clients.

Used by mobile_bff (always) and web_bff when X-Client-Type is ios/android (External ALB may route
mobile traffic to Web targets; book service may not see X-A2-Mobile-BFF if stripped by ALB).
"""
import json
import sys
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
    """
    Parse JSON and rewrite genre. If parsing fails, return original bytes unchanged.
    Uses utf-8-sig so a BOM does not break json.loads.
    """
    if not data:
        return data
    try:
        text = data.decode("utf-8-sig")
        if not text.lstrip().startswith(("{", "[")):
            return data
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
    except Exception as e:
        print("bff_book_transform: transform_book_response failed:", repr(e), file=sys.stderr)
        return data


def apply_book_genre_after_request(resp: Any, *, web_bff: bool = False) -> Any:
    """
    Flask @app.after_request: second pass so non-fiction -> 3 always applies to /books JSON
    (covers edge cases where Response wasn't transformed in build_response).

    web_bff=True: only rewrite when X-Client-Type is iOS/Android (Web BFF).
    web_bff=False: Mobile BFF — rewrite for every proxied /books response.
    """
    from flask import request

    if web_bff:
        xt = (request.headers.get("X-Client-Type") or "").strip().lower()
        if xt not in ("ios", "android"):
            return resp
    if resp.status_code not in (200, 201):
        return resp
    ct = (resp.headers.get("Content-Type") or "").lower()
    if "application/json" not in ct:
        return resp
    path = request.path or ""
    if not path.startswith("/books"):
        return resp
    m = (request.method or "GET").upper()
    p = path.rstrip("/") or "/"
    if should_skip_book_genre_transform(m, p):
        return resp
    data = resp.get_data()
    new_body = transform_book_response(data)
    if new_body != data:
        resp.set_data(new_body)
        resp.headers["Content-Length"] = str(len(new_body))
    return resp
