"""
Web BFF — A1/A2: proxy to Internal ALB; JWT + X-Client-Type: Web on protected routes; /status = OK.
"""
import os
import requests
from flask import Flask, Response, request

import sys

_app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _app_dir)
sys.path.insert(0, os.path.join(_app_dir, ".."))
from shared.client_headers import require_web_client
from shared.jwt_utils import require_jwt

app = Flask(__name__)
# Empty env var would break requests URL; treat as unset
_backend = (os.environ.get("URL_BASE_BACKEND_SERVICES") or "").strip()
BACKEND_BASE = (_backend or "http://localhost:3000").rstrip("/")


def proxy_to_backend(path: str, method: str = "GET", **kwargs):
    url = f"{BACKEND_BASE}{path}"
    if request.query_string:
        url += "?" + request.query_string.decode()
    headers = {
        k: v
        for k, v in request.headers
        if k.lower() not in ("host", "authorization")
    }
    m = (method or "GET").upper()
    # GET/HEAD with a body or Content-Length confuses Flask/Werkzeug (400). Never forward bodies for safe methods.
    if m in ("GET", "HEAD"):
        headers = {
            k: v
            for k, v in headers.items()
            if k.lower()
            not in ("content-length", "content-type", "transfer-encoding")
        }
    elif request.get_data():
        kwargs["data"] = request.get_data()
    try:
        r = requests.request(m, url, timeout=30, headers=headers, **kwargs)
        return r.content, r.status_code, dict(r.headers)
    except requests.RequestException:
        return b"Bad Gateway", 502, {}


def build_response(body, status_code, headers):
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        lk = k.lower()
        if lk in ("content-type", "content-length", "location"):
            resp.headers[k] = v
    return resp


@app.route("/status", methods=["GET"])
def status():
    return Response("OK", status=200, mimetype="text/plain")


@app.route("/customers", methods=["GET", "POST"])
@require_jwt
@require_web_client
def customers():
    body, status_code, headers = proxy_to_backend("/customers", method=request.method)
    return build_response(body, status_code, headers)


@app.route("/customers/<path:subpath>", methods=["GET"])
@require_jwt
@require_web_client
def customer_by_id(subpath):
    body, status_code, headers = proxy_to_backend(f"/customers/{subpath}")
    return build_response(body, status_code, headers)


@app.route("/books", methods=["GET", "POST"])
@require_jwt
@require_web_client
def books():
    body, status_code, headers = proxy_to_backend("/books", method=request.method)
    return build_response(body, status_code, headers)


@app.route("/books/<path:subpath>", methods=["GET", "PUT"])
@require_jwt
@require_web_client
def book_subpath(subpath):
    body, status_code, headers = proxy_to_backend(f"/books/{subpath}", method=request.method)
    return build_response(body, status_code, headers)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 80))
    app.run(host="0.0.0.0", port=port, debug=False)
