"""
Book microservice - exposes /books and /status on port 3000.
Runs on EC2BookstoreB and EC2BookstoreC.
"""
import os
import pymysql
from flask import Flask, request, jsonify

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


@app.route("/status", methods=["GET"])
def status():
    """Health check for ALB."""
    return "", 200


@app.route("/books", methods=["GET"])
def list_books():
    """GET /books"""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT isbn, title, author, genre FROM books")
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/books/<isbn>", methods=["GET"])
def get_book_by_isbn(isbn):
    """GET /books/{ISBN}"""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT isbn, title, author, genre FROM books WHERE isbn = %s", (isbn,)
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return "", 404
        return jsonify(row), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/books/isbn/<isbn>", methods=["GET"])
def get_book_by_isbn_path(isbn):
    """GET /books/isbn/{ISBN} - same as GET /books/{ISBN}"""
    return get_book_by_isbn(isbn)


@app.route("/books", methods=["POST"])
def create_book():
    """POST /books - create book (JSON body)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO books (isbn, title, author, genre) VALUES (%s, %s, %s, %s)",
                (
                    data.get("isbn"),
                    data.get("title"),
                    data.get("author") or "",
                    data.get("genre") or "",
                ),
            )
        conn.close()
        return jsonify(data), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)
