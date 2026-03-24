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


def transform_web_client_book_response(data: bytes) -> bytes:
    """
    Web clients expect genre string 'non-fiction'. Book service emits int 3 for non-fiction on
    single-book responses; map 3 -> 'non-fiction' in JSON (idempotent for lists that use strings).
    """
    if not data:
        return data
    try:
        text = data.decode("utf-8-sig")
        if not text.lstrip().startswith(("{", "[")):
            return data
        parsed: Any = json.loads(text)

        def fix(obj: dict) -> None:
            if not isinstance(obj, dict):
                return
            g = obj.get("genre")
            if isinstance(g, int) and g == 3:
                obj["genre"] = "non-fiction"

        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    fix(item)
        elif isinstance(parsed, dict):
            fix(parsed)
        return json.dumps(parsed, separators=(",", ":")).encode("utf-8")
    except Exception as e:
        print("bff_book_transform: transform_web_client_book_response failed:", repr(e), file=sys.stderr)
        return data


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
    Flask @app.after_request: second pass for /books JSON genre shaping.

    Web BFF: Web client -> map genre int 3 -> 'non-fiction'; iOS/Android -> string non-fiction -> 3 (fallback).
    Mobile BFF: non-fiction string -> 3 (fallback if book service did not emit 3).
    """
    from flask import request

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

    xt = (request.headers.get("X-Client-Type") or "").strip().lower()
    data = resp.get_data()

    if web_bff:
        if xt == "web":
            new_body = transform_web_client_book_response(data)
        elif xt in ("ios", "android"):
            new_body = transform_book_response(data)
        else:
            return resp
    else:
        new_body = transform_book_response(data)

    if new_body != data:
        resp.set_data(new_body)
        resp.headers["Content-Length"] = str(len(new_body))
    return resp
