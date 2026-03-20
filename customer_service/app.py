"""
Customer microservice - exposes /customers and /status on port 3000.
Runs on EC2BookstoreA and EC2BookstoreD.
"""
import os
import pymysql
from flask import Flask, request, jsonify

app = Flask(__name__)

# Database config from environment (passed by docker run -e)
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
    """Health check for ALB. Must return 200."""
    return "", 200


@app.route("/customers", methods=["GET"])
def list_customers():
    """GET /customers or GET /customers?userId=<userId>"""
    user_id = request.args.get("userId")
    try:
        conn = get_db()
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    "SELECT id, userId, name, address, address2, city, state, zipcode FROM customers WHERE userId = %s",
                    (user_id,),
                )
            else:
                cur.execute(
                    "SELECT id, userId, name, address, address2, city, state, zipcode FROM customers"
                )
            rows = cur.fetchall()
        conn.close()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/customers/<int:customer_id>", methods=["GET"])
def get_customer(customer_id):
    """GET /customers/{id}"""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, userId, name, address, address2, city, state, zipcode FROM customers WHERE id = %s",
                (customer_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return "", 404
        return jsonify(row), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/customers", methods=["POST"])
def create_customer():
    """POST /customers - create customer (JSON body)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO customers (userId, name, address, address2, city, state, zipcode)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    data.get("userId"),
                    data.get("name"),
                    data.get("address") or "",
                    data.get("address2") or "",
                    data.get("city") or "",
                    data.get("state") or "",
                    data.get("zipcode") or "",
                ),
            )
            cid = cur.lastrowid
        conn.close()
        return jsonify({"id": cid, **data}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)
