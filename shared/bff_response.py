"""
Shared BFF response helpers (Location rewriting behind ALB).
"""
import os

from flask import request


def absolute_location_header(location_value: str) -> str:
    """
    Backends emit Location: /books/{isbn}. BFF expands to absolute URL for clients that expect it.

    If url.txt uses http://host:80/... but ALB sends Host without :80, set BFF_HTTP_LOCATION_PORT=80 (default)
    so Location matches. Set BFF_HTTP_LOCATION_PORT= empty to omit. Set BFF_PRESERVE_RELATIVE_LOCATION=1
    to pass through relative Location unchanged.
    """
    if not location_value or not isinstance(location_value, str):
        return location_value
    loc = location_value.strip()
    if loc.startswith("http://") or loc.startswith("https://"):
        return loc
    if not loc.startswith("/"):
        return loc
    if os.environ.get("BFF_PRESERVE_RELATIVE_LOCATION", "").strip().lower() in ("1", "true", "yes"):
        return loc
    proto = (request.headers.get("X-Forwarded-Proto") or request.scheme or "http").split(",")[0].strip()
    host = (request.headers.get("Host") or "").split(",")[0].strip()
    if not host:
        return loc
    # Optional explicit port (matches url.txt like http://alb:80 when Host has no port)
    port = os.environ.get("BFF_HTTP_LOCATION_PORT", "").strip()
    if proto == "http" and port and "[" not in host:
        host_part = host.split("@")[-1]
        if ":" not in host_part:
            host = f"{host}:{port}"
    return f"{proto}://{host}{loc}"
