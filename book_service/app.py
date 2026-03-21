"""
Book microservice — A1 REST + A2 deployment (port 3000).
Spec: 17-647 A1 (ISBN, Author, description, genre, price, quantity, summary on GET; LLM async).
"""
from __future__ import annotations

import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Tuple

import pymysql
import requests
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


def get_db():
    return pymysql.connect(**DB_CONFIG)


def row_to_book_json(row: dict, include_summary: bool) -> dict:
    """A1 JSON keys: ISBN, title, Author, description, genre, price, quantity; summary on GET."""
    out = {
        "ISBN": row["isbn"],
        "title": row["title"],
        "Author": row["author"],
        "description": row["description"],
        "genre": row["genre"],
        "price": float(row["price"]) if row["price"] is not None else None,
        "quantity": int(row["quantity"]),
    }
    # GET responses must always include summary (empty until async LLM fills it)
    if include_summary:
        out["summary"] = row.get("summary") or ""
    return out


def get_isbn_from_body(data: dict) -> Optional[str]:
    if not data:
        return None
    return data.get("ISBN") or data.get("isbn")


def validate_price(price: Any) -> Tuple[bool, Optional[Decimal]]:
    if price is None or isinstance(price, bool):
        return False, None
    if isinstance(price, str):
        s = price.strip()
        if not s or not re.match(r"^-?\d+(\.\d+)?$", s):
            return False, None
        try:
            d = Decimal(s)
        except InvalidOperation:
            return False, None
    elif isinstance(price, (int, float)):
        try:
            d = Decimal(str(price))
        except InvalidOperation:
            return False, None
    else:
        return False, None
    if d < 0:
        return False, None
    exp = d.as_tuple().exponent
    if exp < 0 and abs(exp) > 2:
        return False, None
    return True, d


def validate_quantity(q: Any) -> Tuple[bool, Optional[int]]:
    if q is None or isinstance(q, bool):
        return False, None
    if isinstance(q, int) and not isinstance(q, bool):
        return True, q
    if isinstance(q, float) and q.is_integer():
        return True, int(q)
    return False, None


def post_book_required_keys(data: dict) -> bool:
    if not data:
        return False
    isbn = get_isbn_from_body(data)
    need = ["title", "Author", "description", "genre", "price", "quantity"]
    if not isbn:
        return False
    for k in need:
        if k not in data:
            return False
    return True


def put_book_required_keys(data: dict) -> bool:
    return post_book_required_keys(data)


def fetch_book_row(cur, isbn: str) -> Optional[dict]:
    cur.execute(
        "SELECT isbn, title, author, description, genre, price, quantity, summary FROM books WHERE isbn = %s",
        (isbn,),
    )
    return cur.fetchone()


def _call_llm_or_fallback(title: str, author: str, description: str, genre: str) -> str:
    url = os.environ.get("LLM_API_URL") or os.environ.get("OPENAI_API_BASE")
    key = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("GROQ_API_KEY")
    )
    model = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
    if url and key:
        try:
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            body = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Write a concise book summary under 500 words for: title={title!r}, "
                            f"author={author!r}, genre={genre!r}. Description: {description}"
                        ),
                    }
                ],
                "max_tokens": 800,
            }
            r = requests.post(url, json=body, headers=headers, timeout=60)
            r.raise_for_status()
            data = r.json()
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if text and len(text.strip()) > 20:
                return text.strip()[:5000]
        except Exception:
            pass
    return (
        f'"{title}" by {author} ({genre}): {description[:400]}'
        if description
        else f'"{title}" by {author} ({genre}).'
    )


@app.route("/status", methods=["GET"])
def status():
    return Response("OK", status=200, mimetype="text/plain")


@app.route("/books", methods=["GET"])
def list_books():
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT isbn, title, author, description, genre, price, quantity, summary FROM books"
            )
            rows = cur.fetchall()
        conn.close()
        return jsonify([row_to_book_json(r, True) for r in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/books/<isbn>", methods=["GET", "PUT"])
def book_by_isbn(isbn):
    if request.method == "GET":
        try:
            conn = get_db()
            with conn.cursor() as cur:
                row = fetch_book_row(cur, isbn)
            conn.close()
            if not row:
                return "", 404
            return jsonify(row_to_book_json(row, True)), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    data = request.get_json(silent=True)
    if not put_book_required_keys(data):
        return "", 400
    body_isbn = get_isbn_from_body(data)
    if body_isbn != isbn:
        return "", 400
    ok, dprice = validate_price(data.get("price"))
    if not ok:
        return "", 400
    ok_q, qty = validate_quantity(data.get("quantity"))
    if not ok_q:
        return "", 400

    try:
        conn = get_db()
        with conn.cursor() as cur:
            if not fetch_book_row(cur, isbn):
                conn.close()
                return "", 404
            cur.execute(
                """UPDATE books SET title=%s, author=%s, description=%s, genre=%s, price=%s, quantity=%s
                   WHERE isbn=%s""",
                (
                    data["title"],
                    data["Author"],
                    data["description"],
                    data["genre"],
                    str(dprice),
                    qty,
                    isbn,
                ),
            )
            cur.execute(
                "SELECT isbn, title, author, description, genre, price, quantity, summary FROM books WHERE isbn=%s",
                (isbn,),
            )
            row = cur.fetchone()
        conn.close()
        return jsonify(row_to_book_json(row, True)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/books/isbn/<isbn>", methods=["GET"])
def get_book_by_isbn_path(isbn):
    return book_by_isbn(isbn)


@app.route("/books", methods=["POST"])
def create_book():
    data = request.get_json(silent=True)
    if not post_book_required_keys(data):
        return "", 400
    isbn = get_isbn_from_body(data)
    ok, dprice = validate_price(data.get("price"))
    if not ok:
        return "", 400
    ok_q, qty = validate_quantity(data.get("quantity"))
    if not ok_q:
        return "", 400

    try:
        summary_text = _call_llm_or_fallback(
            data["title"],
            data["Author"],
            data["description"],
            data["genre"],
        )
        conn = get_db()
        with conn.cursor() as cur:
            if fetch_book_row(cur, isbn):
                conn.close()
                return jsonify({"message": "This ISBN already exists in the system."}), 422
            cur.execute(
                """INSERT INTO books (isbn, title, author, description, genre, price, quantity, summary)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    isbn,
                    data["title"],
                    data["Author"],
                    data["description"],
                    data["genre"],
                    str(dprice),
                    qty,
                    summary_text,
                ),
            )
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    resp = jsonify(
        {
            "ISBN": isbn,
            "title": data["title"],
            "Author": data["Author"],
            "description": data["description"],
            "genre": data["genre"],
            "price": float(dprice),
            "quantity": qty,
        }
    )
    resp.status_code = 201
    resp.headers["Location"] = f"/books/{isbn}"
    return resp


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)
