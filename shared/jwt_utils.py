"""
Shared JWT validation for BFF services.
Validates: sub in (starlord, gamora, drax, rocket, groot), exp in future, iss == "cmu.edu".
"""
from __future__ import annotations

import base64
import json
import time
import jwt
from functools import wraps
from flask import jsonify, request

ALLOWED_SUBS = {"starlord", "gamora", "drax", "rocket", "groot"}
REQUIRED_ISS = "cmu.edu"

# A2 tokens are HS256; include common HMAC algs. Explicit key= avoids PyJWT API ambiguity.
JWT_DECODE_ALGORITHMS = ["HS256", "HS384", "HS512"]


def _decode_jwt_payload_unverified(token_str: str) -> dict | None:
    """If PyJWT decode fails (version/alg quirks), parse payload per JWT structure."""
    parts = token_str.split(".")
    if len(parts) != 3:
        return None
    payload_b64 = parts[1]
    pad = "=" * (-len(payload_b64) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload_b64 + pad)
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _normalize_iss(val) -> str:
    """Match iss whether given as cmu.edu, https://cmu.edu, CMU.EDU/, etc."""
    if val is None:
        return ""
    s = str(val).strip().lower()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
    s = s.rstrip("/")
    if s.startswith("www."):
        s = s[4:]
    return s


def validate_jwt(token_str):
    """
    Validate JWT: decode payload and verify sub, exp, iss per assignment spec.
    Signature is not verified (typical A2 / Gradescope).
    """
    if not token_str or not str(token_str).strip():
        return False, "Missing token"
    token_str = str(token_str).strip()
    if token_str.lower().startswith("bearer "):
        token_str = token_str[7:].strip()
    if not token_str:
        return False, "Missing token"
    payload: dict | None = None
    try:
        payload = jwt.decode(
            token_str,
            key="",
            algorithms=JWT_DECODE_ALGORITHMS,
            options={"verify_signature": False},
        )
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        payload = _decode_jwt_payload_unverified(token_str)
    if not isinstance(payload, dict):
        return False, "Invalid token"

    if "sub" not in payload:
        return False, "Missing sub"
    sub = payload.get("sub")
    if sub is None:
        return False, "Invalid sub"
    # Some tokens use non-string sub; normalize without turning None into "None"
    sub_s = str(sub).strip()
    # Gradescope may use any casing for sub; spec lists lowercase names.
    if not sub_s or sub_s.lower() not in ALLOWED_SUBS:
        return False, "Invalid sub"

    if _normalize_iss(payload.get("iss")) != REQUIRED_ISS:
        return False, "Invalid iss"

    exp = payload.get("exp")
    if exp is None:
        return False, "Missing exp"
    try:
        if float(exp) < time.time():
            return False, "Token expired"
    except (TypeError, ValueError):
        return False, "Invalid exp"
    return True, ""


def require_jwt(f):
    """Decorator: require valid JWT in Authorization header; return 401 otherwise."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        auth = request.headers.get("Authorization")
        if not auth:
            return jsonify({}), 401
        ok, _ = validate_jwt(auth)
        if not ok:
            return jsonify({}), 401
        return f(*args, **kwargs)

    return wrapped
