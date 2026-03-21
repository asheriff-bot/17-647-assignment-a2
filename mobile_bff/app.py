"""
Mobile BFF — A2: X-Client-Type iOS/Android + JWT; genre non-fiction → 3; strip address fields.
"""
import json
import os
import requests
from flask import Flask, Response, request

import sys

_app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _app_dir)
sys.path.insert(0, os.path.join(_app_dir, ".."))
from shared.client_headers import require_mobile_client
from shared.jwt_utils import require_jwt

app = Flask(__name__)
BACKEND_BASE = os.environ.get("URL_BASE_BACKEND_SERVICES", "http://localhost:3000").rstrip("/")

CUSTOMER_ATTRS_TO_REMOVE = {"address", "address2", "city", "state", "zipcode"}


def proxy_to_backend(path: str, method: str = "GET", **kwargs):
    url = f"{BACKEND_BASE}{path}"
    if request.query_string:
        url += "?" + request.query_string.decode()
    headers = {
        k: v
        for k, v in request.headers
        if k.lower() not in ("host", "authorization")
    }
    if request.get_data():
        kwargs["data"] = request.get_data()
    try:
        r = requests.request(method, url, timeout=30, headers=headers, **kwargs)
        return r.content, r.status_code, dict(r.headers)
    except requests.RequestException:
        return b"Bad Gateway", 502, {}


def _transform_book_obj(obj: dict) -> None:
    if obj.get("genre") == "non-fiction":
        obj["genre"] = 3


def transform_book_response(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8")
        parsed = json.loads(text)
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    _transform_book_obj(item)
        elif isinstance(parsed, dict):
            _transform_book_obj(parsed)
        out = json.dumps(parsed, separators=(",", ":"))
        return out.encode("utf-8")
    except Exception:
        return data


def transform_customer_response(data: bytes) -> bytes:
    try:
        obj = json.loads(data.decode("utf-8"))
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    for k in CUSTOMER_ATTRS_TO_REMOVE:
                        item.pop(k, None)
        elif isinstance(obj, dict):
            for k in CUSTOMER_ATTRS_TO_REMOVE:
                obj.pop(k, None)
        return json.dumps(obj).encode("utf-8")
    except Exception:
        return data


def build_response(body, status_code, headers, apply_book=False, apply_customer=False):
    if body and status_code in (200, 201):
        if apply_book:
            body = transform_book_response(body)
        if apply_customer:
            body = transform_customer_response(body)
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        lk = k.lower()
        if lk in ("content-type", "content-length", "location"):
            resp.headers[k] = v
    if body is not None:
        blen = len(body) if isinstance(body, (bytes, bytearray)) else 0
        resp.headers["Content-Length"] = str(blen)
    return resp


@app.route("/status", methods=["GET"])
def status():
    return Response("OK", status=200, mimetype="text/plain")


@app.route("/customers", methods=["GET", "POST"])
@require_mobile_client
@require_jwt
def customers():
    body, status_code, headers = proxy_to_backend("/customers", method=request.method)
    return build_response(
        body, status_code, headers, apply_book=False, apply_customer=True
    )


@app.route("/customers/<path:subpath>", methods=["GET"])
@require_mobile_client
@require_jwt
def customer_by_id(subpath):
    body, status_code, headers = proxy_to_backend(f"/customers/{subpath}")
    return build_response(
        body, status_code, headers, apply_book=False, apply_customer=True
    )


@app.route("/books", methods=["GET", "POST"])
@require_mobile_client
@require_jwt
def books():
    body, status_code, headers = proxy_to_backend("/books", method=request.method)
    return build_response(body, status_code, headers, apply_book=True, apply_customer=False)


@app.route("/books/<path:subpath>", methods=["GET", "PUT"])
@require_mobile_client
@require_jwt
def book_subpath(subpath):
    body, status_code, headers = proxy_to_backend(f"/books/{subpath}", method=request.method)
    return build_response(body, status_code, headers, apply_book=True, apply_customer=False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 80))
    app.run(host="0.0.0.0", port=port, debug=False)
