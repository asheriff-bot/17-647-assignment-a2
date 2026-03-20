"""
Shared JWT validation for BFF services.
Validates: sub in (starlord, gamora, drax, rocket, groot), exp in future, iss == "cmu.edu".
"""
import os
import time
import jwt
from functools import wraps
from flask import request

ALLOWED_SUBS = {"starlord", "gamora", "drax", "rocket", "groot"}
REQUIRED_ISS = "cmu.edu"


def get_secret():
    return os.environ.get("JWT_SECRET", "cmu-a2-secret")


def validate_jwt(token_str):
    """
    Validate JWT: decode payload and verify sub, exp, iss per assignment spec.
    Returns (ok, error_message).
    """
    if not token_str or not token_str.strip():
        return False, "Missing token"
    token_str = token_str.strip()
    if token_str.lower().startswith("bearer "):
        token_str = token_str[7:].strip()
    try:
        payload = jwt.decode(
            token_str,
            options={"verify_signature": False},
        )
    except jwt.InvalidTokenError:
        return False, "Invalid token"
    if "sub" not in payload:
        return False, "Missing sub"
    if payload.get("sub") not in ALLOWED_SUBS:
        return False, "Invalid sub"
    if payload.get("iss") != REQUIRED_ISS:
        return False, "Invalid iss"
    exp = payload.get("exp")
    if exp is None:
        return False, "Missing exp"
    if exp < time.time():
        return False, "Token expired"
    return True, ""


def require_jwt(f):
    """Decorator: require valid JWT in Authorization header; return 401 otherwise."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        auth = request.headers.get("Authorization")
        if not auth:
            return "", 401
        ok, _ = validate_jwt(auth)
        if not ok:
            return "", 401
        return f(*args, **kwargs)

    return wrapped
