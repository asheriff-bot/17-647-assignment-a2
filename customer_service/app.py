"""
Customer microservice — A1 REST + A2 deployment (port 3000).
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

import pymysql
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
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


def get_db():
    return pymysql.connect(**DB_CONFIG)


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


def post_customer_required(data: dict) -> bool:
    if not data:
        return False
    mandatory = ["userId", "name", "phone", "address", "city", "state", "zipcode"]
    for k in mandatory:
        if k not in data:
            return False
    return True


@app.route("/status", methods=["GET"])
def status():
    return Response("OK", status=200, mimetype="text/plain")


@app.route("/customers", methods=["GET"])
def list_or_query_customers():
    user_id = request.args.get("userId")
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
        return "", 400
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
            return "", 404
        return jsonify(row_to_customer_json(row)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/customers/<customer_id>", methods=["GET"])
def get_customer(customer_id):
    if not str(customer_id).isdigit():
        return "", 400
    cid = int(customer_id)
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
            return "", 404
        return jsonify(row_to_customer_json(row)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/customers", methods=["POST"])
def create_customer():
    data = request.get_json(silent=True)
    if not post_customer_required(data):
        return "", 400
    if not valid_email(data.get("userId", "")):
        return "", 400
    st = (data.get("state") or "").strip().upper()
    if st not in US_STATES:
        return "", 400

    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM customers WHERE userId = %s",
                (data["userId"],),
            )
            if cur.fetchone():
                conn.close()
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
        conn.close()
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)
