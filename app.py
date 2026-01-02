from decimal import Decimal
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = "food-aggregator-secret"
app.url_map.strict_slashes = False

# XAMPP MySQL: user=root, password="" (empty)
# If you have a password: mysql+pymysql://root:YOURPASS@127.0.0.1:3306/food_aggregator
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:@127.0.0.1:3306/food_aggregator"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------- MODELS --------------------
class User(db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone_number = db.Column(db.String(30), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # Admin / Customer / Delivery Agent
    address = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)


class Restaurant(db.Model):
    __tablename__ = "restaurants"
    restaurant_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(140), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Active")
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)


class MenuItem(db.Model):
    __tablename__ = "menu_items"
    menu_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.restaurant_id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(20), nullable=True)  # Food / Drink
    availability = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)

    restaurant = db.relationship("Restaurant", backref=db.backref("menu_items", lazy=True))


class Order(db.Model):
    __tablename__ = "orders"
    order_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.restaurant_id"), nullable=False)

    status = db.Column(db.String(30), nullable=False, default="Placed")
    payment_method = db.Column(db.String(20), nullable=False)  # COD / Online
    delivery_instructions = db.Column(db.String(255), nullable=True)

    placed_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    preparing_at = db.Column(db.DateTime, nullable=True)
    out_for_delivery_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("orders", lazy=True))
    restaurant = db.relationship("Restaurant", backref=db.backref("orders", lazy=True))


class OrderItem(db.Model):
    __tablename__ = "order_items"
    orderitem_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.order_id"), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.menu_id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Numeric(10, 2), nullable=False)  # capture at order time

    order = db.relationship("Order", backref=db.backref("items", lazy=True, cascade="all, delete-orphan"))
    menu_item = db.relationship("MenuItem")


class DeliveryAssignment(db.Model):
    __tablename__ = "delivery_assignments"
    delivery_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.order_id"), nullable=False, unique=True)
    delivery_agent_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="Assigned")

    assigned_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)
    pickup_at = db.Column(db.DateTime, nullable=True)
    dropped_at = db.Column(db.DateTime, nullable=True)
    expected_drop_at = db.Column(db.DateTime, nullable=True)

    order = db.relationship("Order", backref=db.backref("delivery", uselist=False))
    agent = db.relationship("User")


class Review(db.Model):
    __tablename__ = "reviews"
    review_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.restaurant_id"), nullable=True)
    delivery_agent_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)


# -------------------- HELPERS --------------------
def money_str(x) -> str:
    if x is None:
        return "0.00"
    if isinstance(x, Decimal):
        return f"{x:.2f}"
    try:
        return f"{Decimal(str(x)):.2f}"
    except Exception:
        return str(x)


def calc_total(order: Order) -> str:
    total = Decimal("0.00")
    for it in order.items:
        total += Decimal(str(it.price_at_purchase)) * Decimal(str(it.quantity))
    return money_str(total)


# -------------------- ROUTES --------------------
@app.route("/")
def index():
    tab = request.args.get("tab", "users")
    track_order_id = request.args.get("track_order_id")

    users = User.query.order_by(User.user_id.desc()).all()
    restaurants = Restaurant.query.order_by(Restaurant.restaurant_id.desc()).all()
    menu_items = MenuItem.query.order_by(MenuItem.menu_id.desc()).all()

    tracked = None
    if track_order_id:
        try:
            oid = int(track_order_id)
            order = Order.query.get(oid)
            if order:
                tracked = {
                    "order": order,
                    "items": order.items,
                    "total": calc_total(order),
                    "delivery": order.delivery,
                }
            else:
                flash("Order not found.", "error")
        except Exception:
            flash("Invalid order id.", "error")

    return render_template(
        "index.html",
        tab=tab,
        users=users,
        restaurants=restaurants,
        menu_items=menu_items,
        tracked=tracked,
        money_str=money_str,
    )


@app.route("/actions/create_user", methods=["POST"])
def create_user():
    try:
        u = User(
            full_name=request.form["full_name"].strip(),
            email=request.form["email"].strip(),
            phone_number=request.form["phone_number"].strip(),
            type=request.form["type"].strip(),
            address=(request.form.get("address") or "").strip() or None,
        )
        db.session.add(u)
        db.session.commit()
        flash(f"User created (ID: {u.user_id})", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("index", tab="users"))


@app.route("/actions/create_restaurant", methods=["POST"])
def create_restaurant():
    try:
        r = Restaurant(
            name=request.form["name"].strip(),
            address=request.form["address"].strip(),
            status=request.form.get("status", "Active").strip(),
        )
        db.session.add(r)
        db.session.commit()
        flash(f"Restaurant created (ID: {r.restaurant_id})", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("index", tab="restaurants"))


@app.route("/actions/create_menu_item", methods=["POST"])
def create_menu_item():
    try:
        price = Decimal(request.form["price"]).quantize(Decimal("0.01"))
        mi = MenuItem(
            restaurant_id=int(request.form["restaurant_id"]),
            name=request.form["name"].strip(),
            price=price,
            category=request.form.get("category") or None,
            availability=True if request.form.get("availability") == "on" else False,
        )
        db.session.add(mi)
        db.session.commit()
        flash(f"Menu item added (ID: {mi.menu_id})", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("index", tab="menu"))


@app.route("/actions/place_order", methods=["POST"])
def place_order():
    try:
        user_id = int(request.form["user_id"])
        restaurant_id = int(request.form["restaurant_id"])

        user = User.query.get(user_id)
        if not user or user.type != "Customer":
            raise ValueError("Only Customer users can place orders.")

        order = Order(
            user_id=user_id,
            restaurant_id=restaurant_id,
            payment_method=request.form["payment_method"],
            delivery_instructions=(request.form.get("delivery_instructions") or "").strip() or None,
            status="Placed",
        )
        db.session.add(order)
        db.session.flush()

        menu_ids = request.form.getlist("menu_item_id[]")
        qtys = request.form.getlist("quantity[]")

        added = 0
        for mid, q in zip(menu_ids, qtys):
            if not str(mid).strip():
                continue
            menu_item_id = int(mid)
            quantity = int(q)
            if quantity <= 0:
                raise ValueError("Quantity must be > 0")

            mi = MenuItem.query.get(menu_item_id)
            if not mi:
                raise ValueError(f"Menu item not found: {menu_item_id}")
            if mi.restaurant_id != restaurant_id:
                raise ValueError("Menu item does not belong to this restaurant.")
            if not mi.availability:
                raise ValueError("Menu item is unavailable.")

            db.session.add(OrderItem(
                order_id=order.order_id,
                menu_item_id=mi.menu_id,
                quantity=quantity,
                price_at_purchase=mi.price,
            ))
            added += 1

        if added == 0:
            raise ValueError("Add at least one item to place an order.")

        db.session.commit()
        flash(f"Order placed (Order ID: {order.order_id})", "ok")
        return redirect(url_for("index", tab="orders", track_order_id=order.order_id))

    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("index", tab="orders"))


@app.route("/actions/track_order", methods=["POST"])
def track_order():
    try:
        oid = int(request.form["order_id"])
        return redirect(url_for("index", tab="orders", track_order_id=oid))
    except Exception:
        flash("Invalid order id.", "error")
        return redirect(url_for("index", tab="orders"))


@app.route("/actions/update_order_status", methods=["POST"])
def update_order_status():
    try:
        oid = int(request.form["order_id"])
        status = request.form["status"].strip()

        ts_map = {
            "Accepted": "accepted_at",
            "Preparing": "preparing_at",
            "Out for Delivery": "out_for_delivery_at",
            "Delivered": "delivered_at",
            "Cancelled": "cancelled_at",
        }

        order = Order.query.get(oid)
        if not order:
            raise ValueError("Order not found.")

        order.status = status
        if status in ts_map:
            setattr(order, ts_map[status], datetime.utcnow())

        db.session.commit()
        flash("Order status updated.", "ok")
        return redirect(url_for("index", tab="orders", track_order_id=oid))

    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("index", tab="orders"))


@app.route("/actions/assign_delivery", methods=["POST"])
def assign_delivery():
    try:
        oid = int(request.form["order_id"])
        aid = int(request.form["delivery_agent_id"])
        exp_raw = (request.form.get("expected_drop_at") or "").strip()

        agent = User.query.get(aid)
        if not agent or agent.type != "Delivery Agent":
            raise ValueError("delivery_agent_id must be a Delivery Agent user.")

        exp_dt = None
        if exp_raw:
            exp_dt = datetime.strptime(exp_raw, "%Y-%m-%d %H:%M:%S")

        da = DeliveryAssignment(order_id=oid, delivery_agent_id=aid, status="Assigned", expected_drop_at=exp_dt)
        db.session.add(da)
        db.session.commit()
        flash(f"Delivery assigned (Delivery ID: {da.delivery_id})", "ok")

    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")

    return redirect(url_for("index", tab="delivery"))


@app.route("/actions/create_review", methods=["POST"])
def create_review():
    try:
        reviewer_id = int(request.form["reviewer_id"])
        rating = int(request.form["rating"])
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5.")

        target_type = request.form.get("target_type", "restaurant")
        restaurant_id = request.form.get("restaurant_id")
        delivery_agent_id = request.form.get("delivery_agent_id")

        rest_id = None
        agent_id = None
        if target_type == "restaurant":
            if not restaurant_id:
                raise ValueError("Provide restaurant_id for restaurant review.")
            rest_id = int(restaurant_id)
        else:
            if not delivery_agent_id:
                raise ValueError("Provide delivery_agent_id for agent review.")
            agent_id = int(delivery_agent_id)
            agent = User.query.get(agent_id)
            if not agent or agent.type != "Delivery Agent":
                raise ValueError("delivery_agent_id must be a Delivery Agent user.")

        rv = Review(
            reviewer_id=reviewer_id,
            restaurant_id=rest_id,
            delivery_agent_id=agent_id,
            rating=rating,
            comment=(request.form.get("comment") or "").strip() or None,
        )
        db.session.add(rv)
        db.session.commit()
        flash(f"Review submitted (Review ID: {rv.review_id})", "ok")

    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")

    return redirect(url_for("index", tab="reviews"))


@app.route("/test")
def test():
    try:
        db.session.execute(db.text("SELECT 1"))
        return "DB Connected"
    except Exception as e:
        return f"DB NOT Connected: {e}"


# -------------------- RUN --------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("DB init OK (tables ensured).")

    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)