import os
from decimal import Decimal
from datetime import datetime

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import mysql.connector


app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)


DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DB", "food_aggregator"),
}


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


def to_jsonable(value):
    if isinstance(value, Decimal):
        return format(value, "f")  # keep as string for exactness in JSON
    if isinstance(value, (datetime, )):
        return value.isoformat()
    return value


def json_row(row: dict):
    return {k: to_jsonable(v) for k, v in row.items()}


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


# -------------------------
# Users
# -------------------------
@app.post("/api/users")
def create_user():
    body = request.get_json(force=True, silent=True) or {}
    full_name = body.get("full_name")
    email = body.get("email")
    phone_number = body.get("phone_number")
    user_type = body.get("type")
    address = body.get("address")

    if not full_name or not email or not phone_number or not user_type:
        return jsonify({"error": "full_name, email, phone_number, type are required"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (full_name, email, phone_number, type, address)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (full_name, email, phone_number, user_type, address),
        )
        conn.commit()
        return jsonify({"user_id": cur.lastrowid}), 201
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


@app.get("/api/users")
def list_users():
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users ORDER BY user_id DESC")
        rows = [json_row(r) for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        conn.close()


# -------------------------
# Restaurants
# -------------------------
@app.post("/api/restaurants")
def create_restaurant():
    body = request.get_json(force=True, silent=True) or {}
    name = body.get("name")
    address = body.get("address")
    status = body.get("status", "Active")

    if not name or not address:
        return jsonify({"error": "name and address are required"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO restaurants (name, address, status) VALUES (%s, %s, %s)",
            (name, address, status),
        )
        conn.commit()
        return jsonify({"restaurant_id": cur.lastrowid}), 201
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


@app.get("/api/restaurants")
def list_restaurants():
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM restaurants ORDER BY restaurant_id DESC")
        rows = [json_row(r) for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        conn.close()


# -------------------------
# Menu items
# -------------------------
@app.post("/api/menu-items")
def create_menu_item():
    body = request.get_json(force=True, silent=True) or {}
    restaurant_id = body.get("restaurant_id")
    name = body.get("name")
    price = body.get("price")
    category = body.get("category")
    availability = body.get("availability", 1)

    if not restaurant_id or not name or price is None:
        return jsonify({"error": "restaurant_id, name, price are required"}), 400

    try:
        price_dec = Decimal(str(price)).quantize(Decimal("0.01"))
    except Exception:
        return jsonify({"error": "Invalid price"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO menu_items (restaurant_id, name, price, category, availability)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (int(restaurant_id), name, price_dec, category, 1 if availability else 0),
        )
        conn.commit()
        return jsonify({"menu_id": cur.lastrowid}), 201
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


@app.get("/api/restaurants/<int:restaurant_id>/menu")
def get_menu(restaurant_id: int):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT menu_id, restaurant_id, name, price, category, availability
            FROM menu_items
            WHERE restaurant_id = %s
            ORDER BY menu_id DESC
            """,
            (restaurant_id,),
        )
        rows = [json_row(r) for r in cur.fetchall()]
        return jsonify(rows)
    finally:
        conn.close()


# -------------------------
# Orders
# -------------------------
@app.post("/api/orders")
def place_order():
    body = request.get_json(force=True, silent=True) or {}
    user_id = body.get("user_id")
    restaurant_id = body.get("restaurant_id")
    payment_method = body.get("payment_method")
    delivery_instructions = body.get("delivery_instructions")
    items = body.get("items", [])

    if not user_id or not restaurant_id or not payment_method or not isinstance(items, list) or len(items) == 0:
        return jsonify({"error": "user_id, restaurant_id, payment_method, items[] required"}), 400

    conn = get_conn()
    try:
        conn.start_transaction()
        cur = conn.cursor()

        # Create order (trigger enforces user is Customer)
        cur.execute(
            """
            INSERT INTO orders (user_id, restaurant_id, payment_method, delivery_instructions, status)
            VALUES (%s, %s, %s, %s, 'Placed')
            """,
            (int(user_id), int(restaurant_id), payment_method, delivery_instructions),
        )
        order_id = cur.lastrowid

        # Insert items with price captured at purchase time
        get_menu = conn.cursor(dictionary=True)
        insert_item = conn.cursor()

        for it in items:
            menu_item_id = it.get("menu_item_id")
            quantity = it.get("quantity")

            if not menu_item_id or not isinstance(quantity, int) or quantity <= 0:
                raise ValueError("Each item must have menu_item_id and integer quantity > 0")

            get_menu.execute(
                """
                SELECT menu_id, restaurant_id, price, availability
                FROM menu_items
                WHERE menu_id = %s
                """,
                (int(menu_item_id),),
            )
            menu = get_menu.fetchone()
            if not menu:
                raise ValueError(f"Menu item not found: {menu_item_id}")
            if int(menu["restaurant_id"]) != int(restaurant_id):
                raise ValueError(f"Menu item {menu_item_id} does not belong to restaurant {restaurant_id}")
            if int(menu["availability"]) != 1:
                raise ValueError(f"Menu item {menu_item_id} is unavailable")

            insert_item.execute(
                """
                INSERT INTO order_items (order_id, menu_item_id, quantity, price_at_purchase)
                VALUES (%s, %s, %s, %s)
                """,
                (order_id, int(menu_item_id), int(quantity), menu["price"]),
            )

        conn.commit()
        return jsonify({"order_id": order_id}), 201

    except (mysql.connector.Error, ValueError) as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


@app.get("/api/orders/<int:order_id>")
def get_order(order_id: int):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        order = cur.fetchone()
        if not order:
            return jsonify({"error": "Order not found"}), 404

        cur.execute(
            """
            SELECT
              oi.orderitem_id,
              oi.menu_item_id,
              mi.name AS menu_name,
              oi.quantity,
              oi.price_at_purchase,
              (oi.quantity * oi.price_at_purchase) AS line_total
            FROM order_items oi
            JOIN menu_items mi ON mi.menu_id = oi.menu_item_id
            WHERE oi.order_id = %s
            ORDER BY oi.orderitem_id ASC
            """,
            (order_id,),
        )
        items = [json_row(r) for r in cur.fetchall()]

        cur.execute("SELECT total FROM v_order_totals WHERE order_id = %s", (order_id,))
        total_row = cur.fetchone()
        total = total_row["total"] if total_row else Decimal("0.00")

        cur.execute("SELECT * FROM delivery_assignments WHERE order_id = %s", (order_id,))
        delivery = cur.fetchone()

        return jsonify({
            "order": json_row(order),
            "items": items,
            "total": to_jsonable(total),
            "delivery": json_row(delivery) if delivery else None
        })
    finally:
        conn.close()


@app.post("/api/orders/<int:order_id>/status")
def update_order_status(order_id: int):
    body = request.get_json(force=True, silent=True) or {}
    status = body.get("status")
    if not status:
        return jsonify({"error": "status required"}), 400

    # Map status -> timestamp column
    fields = {
        "Accepted": "accepted_at",
        "Preparing": "preparing_at",
        "Out for Delivery": "out_for_delivery_at",
        "Delivered": "delivered_at",
        "Cancelled": "cancelled_at",
    }

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT order_id FROM orders WHERE order_id = %s", (order_id,))
        if not cur.fetchone():
            return jsonify({"error": "Order not found"}), 404

        ts_field = fields.get(status)
        if ts_field:
            cur.execute(
                f"UPDATE orders SET status = %s, {ts_field} = NOW() WHERE order_id = %s",
                (status, order_id),
            )
        else:
            cur.execute(
                "UPDATE orders SET status = %s WHERE order_id = %s",
                (status, order_id),
            )

        conn.commit()
        return jsonify({"ok": True})
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


# -------------------------
# Delivery assignment
# -------------------------
@app.post("/api/deliveries/assign")
def assign_delivery():
    body = request.get_json(force=True, silent=True) or {}
    order_id = body.get("order_id")
    delivery_agent_id = body.get("delivery_agent_id")
    expected_drop_at = body.get("expected_drop_at")  # optional ISO-like string

    if not order_id or not delivery_agent_id:
        return jsonify({"error": "order_id and delivery_agent_id required"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO delivery_assignments (order_id, delivery_agent_id, status, expected_drop_at)
            VALUES (%s, %s, 'Assigned', %s)
            """,
            (int(order_id), int(delivery_agent_id), expected_drop_at),
        )
        conn.commit()
        return jsonify({"delivery_id": cur.lastrowid}), 201
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


# -------------------------
# Reviews
# -------------------------
@app.post("/api/reviews")
def create_review():
    body = request.get_json(force=True, silent=True) or {}
    reviewer_id = body.get("reviewer_id")
    restaurant_id = body.get("restaurant_id")
    delivery_agent_id = body.get("delivery_agent_id")
    rating = body.get("rating")
    comment = body.get("comment")

    if not reviewer_id or rating is None:
        return jsonify({"error": "reviewer_id and rating required"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO reviews (reviewer_id, restaurant_id, delivery_agent_id, rating, comment)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (int(reviewer_id),
             int(restaurant_id) if restaurant_id else None,
             int(delivery_agent_id) if delivery_agent_id else None,
             int(rating),
             comment),
        )
        conn.commit()
        return jsonify({"review_id": cur.lastrowid}), 201
    except mysql.connector.Error as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()


@app.get("/api/reviews")
def list_reviews():
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM reviews ORDER BY review_id DESC")
        return jsonify([json_row(r) for r in cur.fetchall()])
    finally:
        conn.close()


if __name__ == "__main__":
    # Flask dev server
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)