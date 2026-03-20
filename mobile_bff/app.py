"""
Mobile BFF - Backend for iOS/Android. Port 80.
Requires X-Client-Type: iOS or Android (ALB) and valid JWT.
Forwards to backend; transforms: book response replace "non-fiction" with 3;
customer response remove address, address2, city, state, zipcode.
"""
import os
import json
import requests
from flask import Flask, request, Response

import sys
_app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _app_dir)
sys.path.insert(0, os.path.join(_app_dir, ".."))
from shared.jwt_utils import require_jwt

app = Flask(__name__)
BACKEND_BASE = os.environ.get("URL_BASE_BACKEND_SERVICES", "http://localhost:3000").rstrip("/")

CUSTOMER_ATTRS_TO_REMOVE = {"address", "address2", "city", "state", "zipcode"}


def proxy_to_backend(path: str, method: str = "GET", **kwargs):
    url = f"{BACKEND_BASE}{path}"
    if request.query_string:
        url += "?" + request.query_string.decode()
    headers = {k: v for k, v in request.headers if k.lower() not in ("host", "authorization")}
    if request.get_data():
        kwargs["data"] = request.get_data()
    try:
        r = requests.request(method, url, timeout=10, headers=headers, **kwargs)
        return r.content, r.status_code, dict(r.headers)
    except requests.RequestException:
        return b"Bad Gateway", 502, {}


def transform_book_response(data: bytes) -> bytes:
    """Replace 'non-fiction' with 3 in book response body."""
    try:
        text = data.decode("utf-8")
        text = text.replace('"non-fiction"', "3").replace("non-fiction", "3")
        return text.encode("utf-8")
    except Exception:
        return data


def transform_customer_response(data: bytes) -> bytes:
    """Remove address, address2, city, state, zipcode from customer response."""
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


@app.route("/status", methods=["GET"])
def status():
    return "", 200


@app.route("/customers", methods=["GET", "POST"])
@require_jwt
def customers():
    body, status_code, headers = proxy_to_backend("/customers", method=request.method)
    if status_code == 200 and body:
        body = transform_customer_response(body)
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        if k.lower() in ("content-type", "content-length"):
            resp.headers[k] = v
    if body:
        resp.headers["Content-Length"] = str(len(body))
    return resp


@app.route("/customers/<path:subpath>", methods=["GET"])
@require_jwt
def customer_by_id(subpath):
    body, status_code, headers = proxy_to_backend(f"/customers/{subpath}")
    if status_code == 200 and body:
        body = transform_customer_response(body)
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        if k.lower() in ("content-type", "content-length"):
            resp.headers[k] = v
    if body:
        resp.headers["Content-Length"] = str(len(body))
    return resp


@app.route("/books", methods=["GET", "POST"])
@require_jwt
def books():
    body, status_code, headers = proxy_to_backend("/books", method=request.method)
    if status_code == 200 and body:
        body = transform_book_response(body)
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        if k.lower() in ("content-type", "content-length"):
            resp.headers[k] = v
    if body:
        resp.headers["Content-Length"] = str(len(body))
    return resp


@app.route("/books/<path:subpath>", methods=["GET"])
@require_jwt
def book_by_isbn(subpath):
    body, status_code, headers = proxy_to_backend(f"/books/{subpath}")
    if status_code == 200 and body:
        body = transform_book_response(body)
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        if k.lower() in ("content-type", "content-length"):
            resp.headers[k] = v
    if body:
        resp.headers["Content-Length"] = str(len(body))
    return resp


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 80))
    app.run(host="0.0.0.0", port=port, debug=False)
