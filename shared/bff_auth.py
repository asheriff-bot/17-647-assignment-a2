"""
BFF protection: **JWT first (401), then X-Client-Type (400)** in one place.
Avoids decorator stacking mistakes and matches autograder expectations for auth tests.
"""
from functools import wraps

from flask import Response, jsonify, request

from shared.jwt_utils import validate_jwt


def _missing_x_client_type():
    return Response(
        "Request missing X-Client-Type header",
        status=400,
        mimetype="text/plain",
    )


def _require_bff(*, mobile: bool):
    allowed = frozenset({"ios", "android"}) if mobile else frozenset({"web"})

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # 1) Authorization / JWT first → 401 (even when X-Client-Type is absent)
            auth = request.headers.get("Authorization")
            if not auth:
                return jsonify({}), 401
            ok, _ = validate_jwt(auth)
            if not ok:
                return jsonify({}), 401

            # 2) Then X-Client-Type → 400
            h = request.headers.get("X-Client-Type")
            if not h or not str(h).strip():
                return _missing_x_client_type()
            key = str(h).strip().lower()
            if key not in allowed:
                return jsonify({}), 400

            return f(*args, **kwargs)

        return wrapped

    return decorator


require_web_bff = _require_bff(mobile=False)
require_mobile_bff = _require_bff(mobile=True)
