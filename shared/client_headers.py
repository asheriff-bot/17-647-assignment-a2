"""
BFF header checks — match External ALB behavior (A2).
/status is public (no X-Client-Type, no JWT).
"""
from functools import wraps

from flask import Response, request


def _missing_client_type_response():
    return Response(
        "Request missing X-Client-Type header",
        status=400,
        mimetype="text/plain",
    )


def require_x_client_type(*allowed_values: str):
    """Require X-Client-Type header; exact match to one of allowed_values (case-sensitive per ALB)."""

    allowed = set(allowed_values)

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            h = request.headers.get("X-Client-Type")
            if not h:
                return _missing_client_type_response()
            if h not in allowed:
                return "", 400
            return f(*args, **kwargs)

        return wrapped

    return decorator


# External ALB rules: Web | iOS | Android
require_web_client = require_x_client_type("Web")
require_mobile_client = require_x_client_type("iOS", "Android")
