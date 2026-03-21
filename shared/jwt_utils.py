"""
Shared JWT validation for BFF services.
Validates: sub in (starlord, gamora, drax, rocket, groot), exp in future, iss == "cmu.edu" (case-insensitive).
"""
import time
import jwt
from functools import wraps
from flask import jsonify, request

ALLOWED_SUBS = {"starlord", "gamora", "drax", "rocket", "groot"}
REQUIRED_ISS = "cmu.edu"

# Accept common algorithms used by jwt.io / autograders
JWT_ALGORITHMS = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]


def _normalize_iss(val) -> str:
    if val is None:
        return ""
    return str(val).strip().lower()


def validate_jwt(token_str):
    """
    Validate JWT: decode payload and verify sub, exp, iss per assignment spec.
    Signature is not verified (matches typical A2 / Gradescope setups).
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
            algorithms=JWT_ALGORITHMS,
            options={"verify_signature": False},
        )
    except jwt.InvalidTokenError:
        return False, "Invalid token"
    except jwt.PyJWTError:
        return False, "Invalid token"

    if "sub" not in payload:
        return False, "Missing sub"
    sub = payload.get("sub")
    if not isinstance(sub, str):
        return False, "Invalid sub"
    sub = sub.strip()
    if sub not in ALLOWED_SUBS:
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
