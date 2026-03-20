"""
Web BFF - Backend for Web frontend. Port 80.
Requires X-Client-Type: Web (enforced by ALB) and valid JWT.
Forwards /customers and /books to Internal ALB (backend base URL) with no response transformation.
"""
import os
import requests
from flask import Flask, request, Response

# Add parent (local) and cwd (Docker) so shared.jwt_utils is found
import sys
_app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _app_dir)
sys.path.insert(0, os.path.join(_app_dir, ".."))
from shared.jwt_utils import require_jwt

app = Flask(__name__)
BACKEND_BASE = os.environ.get("URL_BASE_BACKEND_SERVICES", "http://localhost:3000").rstrip("/")


def proxy_to_backend(path: str, method: str = "GET", **kwargs):
    """Forward request to backend and return (body, status_code, headers)."""
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


@app.route("/status", methods=["GET"])
def status():
    """Health check - no JWT required for ALB."""
    return "", 200


@app.route("/customers", methods=["GET", "POST"])
@require_jwt
def customers():
    body, status_code, headers = proxy_to_backend("/customers", method=request.method)
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        if k.lower() in ("content-type", "content-length"):
            resp.headers[k] = v
    return resp


@app.route("/customers/<path:subpath>", methods=["GET"])
@require_jwt
def customer_by_id(subpath):
    body, status_code, headers = proxy_to_backend(f"/customers/{subpath}")
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        if k.lower() in ("content-type", "content-length"):
            resp.headers[k] = v
    return resp


@app.route("/books", methods=["GET", "POST"])
@require_jwt
def books():
    body, status_code, headers = proxy_to_backend("/books", method=request.method)
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        if k.lower() in ("content-type", "content-length"):
            resp.headers[k] = v
    return resp


@app.route("/books/<path:subpath>", methods=["GET"])
@require_jwt
def book_by_isbn(subpath):
    body, status_code, headers = proxy_to_backend(f"/books/{subpath}")
    resp = Response(body, status=status_code)
    for k, v in headers.items():
        if k.lower() in ("content-type", "content-length"):
            resp.headers[k] = v
    return resp


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 80))
    app.run(host="0.0.0.0", port=port, debug=False)
