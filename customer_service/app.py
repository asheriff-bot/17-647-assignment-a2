"""
Customer microservice — A1 REST + A2 deployment (port 3000).
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional
from urllib.parse import unquote

import pymysql
from pymysql.err import IntegrityError
from flask import Flask, Response, jsonify, request

app = Flask(__name__)
app.url_map.strict_slashes = False

def _db_host() -> str:
    return (os.environ.get("DB_HOST") or os.environ.get("DB_ENDPOINT") or "localhost").strip()


DB_CONFIG = {
    "host": _db_host(),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "bookstore"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC",
}

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
# Path segment must be a plain integer id (invalid shapes → 400 per A1)
_CUSTOMER_PATH_ID = re.compile(r"^[+-]?\d+$")


def get_db():
    return pymysql.connect(**DB_CONFIG)


def _read_json_dict():
    data = request.get_json(force=True, silent=True)
    return data if isinstance(data, dict) else None


def row_to_customer_json(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "userId": row["userId"],
        "name": row["name"],
        "phone": row["phone"],
        "address": row["address"],
        "address2": row["address2"] if row.get("address2") is not None else "",
        "city": row["city"],
        "state": row["state"],
        "zipcode": row["zipcode"],
    }


def valid_email(s: str) -> bool:
    return bool(s and EMAIL_RE.match(s))


def get_user_id_query_param() -> Optional[str]:
    """
    Read userId from the raw query string using unquote (not form-style unquote_plus).
    Werkzeug/request.args treats '+' as space, which breaks emails like user+tag@domain.com.
    """
    raw = request.query_string.decode("utf-8", errors="replace")
    if not raw:
        return None
    for segment in raw.split("&"):
        if not segment or "=" not in segment:
            continue
        key, _, val = segment.partition("=")
        key_dec = unquote(key.strip(), errors="replace").strip()
        if key_dec.lower() in ("userid", "user_id"):
            return unquote(val, errors="replace").strip()
    return None


def normalize_customer_post_body(data: dict) -> None:
    """Map alternate JSON keys (snake_case, PascalCase) to A1 canonical names."""
    aliases = (
        ("userId", ("user_id", "UserId", "USERID", "UserID", "userID", "email", "Email")),
        ("name", ("Name",)),
        ("phone", ("Phone",)),
        ("address", ("Address",)),
        ("address2", ("Address2",)),
        ("city", ("City",)),
        ("state", ("State",)),
        ("zipcode", ("zipCode", "Zipcode", "ZipCode", "ZIPCODE")),
    )
    for canonical, alts in aliases:
        if canonical in data and data.get(canonical) is not None:
            continue
        for a in alts:
            if a in data:
                data[canonical] = data[a]
                break


def canonical_email_user_id(v: Any) -> Optional[str]:
    """Strip + lowercase for storage and duplicate checks (matches typical UNIQUE email semantics)."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s.lower()


def _non_empty_scalar(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str) and not v.strip():
        return False
    return True


def post_customer_required(data: dict) -> bool:
    if not data:
        return False
    mandatory = ["userId", "name", "phone", "address", "city", "state", "zipcode"]
    for k in mandatory:
        if k not in data:
            return False
        if not _non_empty_scalar(data.get(k)):
            return False
    return True


@app.route("/status", methods=["GET"])
def status():
    return Response("OK", status=200, mimetype="text/plain")


@app.route("/customers", methods=["GET"])
def list_or_query_customers():
    user_id = get_user_id_query_param()
    if user_id is None:
        user_id = request.args.get("userId")
    if user_id is not None:
        stripped = str(user_id).strip()
        if not stripped:
            return jsonify({}), 400
        user_id = canonical_email_user_id(stripped)
        if not user_id:
            return jsonify({}), 400
    if user_id is None:
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, userId, name, phone, address, address2, city, state, zipcode FROM customers"
                )
                rows = cur.fetchall()
            conn.close()
            return jsonify([row_to_customer_json(r) for r in rows]), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if not valid_email(user_id):
        return jsonify({}), 400
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, userId, name, phone, address, address2, city, state, zipcode FROM customers WHERE userId = %s",
                (user_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({}), 404
        return jsonify(row_to_customer_json(row)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/customers/<customer_id>", methods=["GET"])
def get_customer(customer_id):
    s = str(customer_id).strip()
    if not _CUSTOMER_PATH_ID.match(s):
        return jsonify({}), 400
    try:
        cid = int(s, 10)
    except ValueError:
        return jsonify({}), 400
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, userId, name, phone, address, address2, city, state, zipcode FROM customers WHERE id = %s",
                (cid,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({}), 404
        return jsonify(row_to_customer_json(row)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/customers", methods=["POST"])
def create_customer():
    data = _read_json_dict()
    if data is None:
        return jsonify({}), 400
    normalize_customer_post_body(data)
    uid = canonical_email_user_id(data.get("userId"))
    if uid:
        data["userId"] = uid
    if not post_customer_required(data):
        return jsonify({}), 400
    if not valid_email(data.get("userId", "")):
        return jsonify({}), 400
    st = (data.get("state") or "").strip().upper()
    if st not in US_STATES:
        return jsonify({}), 400

    conn = None
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM customers WHERE userId = %s",
                (data["userId"],),
            )
            if cur.fetchone():
                return jsonify({"message": "This user ID already exists in the system."}), 422
            cur.execute(
                """INSERT INTO customers (userId, name, phone, address, address2, city, state, zipcode)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    data["userId"],
                    data["name"],
                    data["phone"],
                    data["address"],
                    data.get("address2") if data.get("address2") is not None else "",
                    data["city"],
                    st,
                    data["zipcode"],
                ),
            )
            cid = cur.lastrowid
        body = row_to_customer_json(
            {
                "id": cid,
                "userId": data["userId"],
                "name": data["name"],
                "phone": data["phone"],
                "address": data["address"],
                "address2": data.get("address2") or "",
                "city": data["city"],
                "state": st,
                "zipcode": data["zipcode"],
            }
        )
        resp = jsonify(body)
        resp.status_code = 201
        resp.headers["Location"] = f"/customers/{cid}"
        return resp
    except IntegrityError as e:
        if e.args and e.args[0] == 1062:
            return jsonify({"message": "This user ID already exists in the system."}), 422
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)
