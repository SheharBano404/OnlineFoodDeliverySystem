from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timedelta, timezone

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, g, abort
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = "food-aggregator-secret"
app.url_map.strict_slashes = False

# XAMPP MySQL default:
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
    type = db.Column(db.String(50), nullable=False)  # Admin / Customer / Delivery Agent / Restaurant Owner
    password_hash = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)


class Restaurant(db.Model):
    __tablename__ = "restaurants"
    restaurant_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    name = db.Column(db.String(140), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Active")
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)

    owner = db.relationship("User", foreign_keys=[owner_id])


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
    price_at_purchase = db.Column(db.Numeric(10, 2), nullable=False)

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


class OrderStatusHistory(db.Model):
    __tablename__ = "order_status_history"
    history_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.order_id"), nullable=False)
    status = db.Column(db.String(40), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)

    actor = db.relationship("User")
    order = db.relationship("Order", backref=db.backref("history", lazy=True, cascade="all, delete-orphan"))


class DeliveryLocation(db.Model):
    __tablename__ = "delivery_locations"
    location_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey("delivery_assignments.delivery_id"), nullable=False)
    lat = db.Column(db.Numeric(10, 7), nullable=False)
    lng = db.Column(db.Numeric(10, 7), nullable=False)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.current_timestamp(), nullable=False)

    delivery = db.relationship("DeliveryAssignment", backref=db.backref("locations", lazy=True, cascade="all, delete-orphan"))


# -------------------- HELPERS --------------------
def money_str(x) -> str:
    if x is None:
        return "0.00"
    try:
        return f"{Decimal(str(x)):.2f}"
    except Exception:
        return str(x)


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def calc_order_total(order: Order) -> Decimal:
    total = Decimal("0.00")
    for it in order.items:
        total += Decimal(str(it.price_at_purchase)) * Decimal(str(it.quantity))
    return total


def log_history(order_id: int, status: str, actor_user_id: int | None, note: str | None = None) -> None:
    db.session.add(OrderStatusHistory(order_id=order_id, status=status, actor_user_id=actor_user_id, note=note))


def eta_for_order(order: Order) -> tuple[str, str]:
    """
    Returns (label, detail).
    """
    if order.status in ("Delivered", "Cancelled"):
        return ("ETA", "—")

    # Prefer admin-set expected drop time
    if order.delivery and order.delivery.expected_drop_at:
        delta = order.delivery.expected_drop_at - now_utc()
        mins = int(delta.total_seconds() // 60)
        if mins <= 0:
            return ("ETA", "Any moment now")
        return ("ETA", f"{mins} min")

    # fallback heuristic
    base = order.placed_at or now_utc()
    minutes_map = {
        "Placed": 45,
        "Accepted": 40,
        "Preparing": 30,
        "Out for Delivery": 15,
    }
    target = base + timedelta(minutes=minutes_map.get(order.status, 45))
    delta = target - now_utc()
    mins = int(delta.total_seconds() // 60)
    if mins <= 0:
        return ("ETA", "Soon")
    return ("ETA", f"{mins} min (estimated)")


def login_required(fn):
    def wrapper(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


def role_required(*roles: str):
    def deco(fn):
        def wrapper(*args, **kwargs):
            if not g.user:
                return redirect(url_for("login", next=request.path))
            if g.user.type not in roles:
                abort(403)
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco


@app.before_request
def load_user():
    uid = session.get("user_id")
    g.user = User.query.get(uid) if uid else None


@app.context_processor
def inject_globals():
    return dict(money_str=money_str)


# -------------------- SEED DATA --------------------
def seed_if_empty():
    if User.query.count() > 0:
        return

    # Admin
    admin = User(
        full_name="System Admin",
        email="admin@fa.local",
        phone_number="0300-0000000",
        type="Admin",
        password_hash=generate_password_hash("admin123"),
        address="HQ",
    )
    db.session.add(admin)
    db.session.flush()

    # Owners
    owners = []
    for i in range(1, 6):
        o = User(
            full_name=f"Owner {i}",
            email=f"owner{i}@fa.local",
            phone_number=f"0311-000000{i}",
            type="Restaurant Owner",
            password_hash=generate_password_hash("owner123"),
            address="City Center",
        )
        owners.append(o)
        db.session.add(o)
    db.session.flush()

    # Restaurants (>=5 active)
    rest_names = ["Karachi Bites", "Lahore Grill", "Islamabad Cafe", "Peshawar Tikka", "Quetta Kitchen"]
    restaurants = []
    for i in range(5):
        r = Restaurant(
            owner_id=owners[i].user_id,
            name=rest_names[i],
            address=f"Main Road Block {i+1}",
            status="Active",
        )
        restaurants.append(r)
        db.session.add(r)
    db.session.flush()

    # Menu items (5 per restaurant)
    menu_pack = [
        ("Chicken Burger", "Food", "499.00"),
        ("Zinger Wrap", "Food", "549.00"),
        ("Chicken Biryani", "Food", "399.00"),
        ("Fries", "Food", "199.00"),
        ("Cold Drink", "Drink", "120.00"),
    ]
    for r in restaurants:
        for name, cat, price in menu_pack:
            db.session.add(MenuItem(
                restaurant_id=r.restaurant_id,
                name=name,
                category=cat,
                price=Decimal(price),
                availability=True,
            ))

    # Delivery agents (10)
    for i in range(1, 11):
        db.session.add(User(
            full_name=f"Rider {i}",
            email=f"agent{i}@fa.local",
            phone_number=f"0322-00000{i:02d}",
            type="Delivery Agent",
            password_hash=generate_password_hash("agent123"),
            address="Near Hub",
        ))

    # Customers (5)
    for i in range(1, 6):
        db.session.add(User(
            full_name=f"Customer {i}",
            email=f"cust{i}@fa.local",
            phone_number=f"0333-000000{i}",
            type="Customer",
            password_hash=generate_password_hash("cust123"),
            address="Some Street",
        ))

    db.session.commit()


# -------------------- AUTH --------------------
@app.route("/")
def home():
    if not g.user:
        return redirect(url_for("login"))
    return redirect(url_for("role_redirect"))


@app.route("/go")
@login_required
def role_redirect():
    t = g.user.type
    if t == "Admin":
        return redirect(url_for("admin_dashboard"))
    if t == "Customer":
        return redirect(url_for("customer_restaurants"))
    if t == "Delivery Agent":
        return redirect(url_for("agent_dashboard"))
    if t == "Restaurant Owner":
        return redirect(url_for("owner_dashboard"))
    abort(403)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("role_redirect"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        u = User.query.filter(func.lower(User.email) == email).first()
        if not u or not check_password_hash(u.password_hash, password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session["user_id"] = u.user_id
        return redirect(url_for("role_redirect"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------------------- ADMIN --------------------
@app.route("/admin")
@role_required("Admin")
def admin_dashboard():
    active_rest = Restaurant.query.filter_by(status="Active").count()
    total_rest = Restaurant.query.count()
    total_agents = User.query.filter_by(type="Delivery Agent").count()
    recent_orders = Order.query.order_by(Order.order_id.desc()).limit(10).all()

    return render_template(
        "admin/dashboard.html",
        active_rest=active_rest,
        total_rest=total_rest,
        total_agents=total_agents,
        recent_orders=recent_orders,
    )


@app.route("/admin/restaurants", methods=["GET", "POST"])
@role_required("Admin")
def admin_restaurants():
    owners = User.query.filter_by(type="Restaurant Owner").order_by(User.user_id.desc()).all()

    if request.method == "POST":
        try:
            r = Restaurant(
                name=request.form["name"].strip(),
                address=request.form["address"].strip(),
                status=request.form.get("status", "Active"),
                owner_id=int(request.form["owner_id"]) if request.form.get("owner_id") else None
            )
            db.session.add(r)
            db.session.commit()
            flash("Restaurant created.", "ok")
        except Exception as e:
            db.session.rollback()
            flash(str(e), "error")
        return redirect(url_for("admin_restaurants"))

    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()

    query = Restaurant.query
    if status in ("Active", "Inactive"):
        query = query.filter_by(status=status)
    if q:
        query = query.filter(Restaurant.name.like(f"%{q}%"))

    restaurants = query.order_by(Restaurant.restaurant_id.desc()).all()
    return render_template("admin/restaurants.html", restaurants=restaurants, owners=owners, q=q, status=status)


@app.route("/admin/restaurants/<int:rid>/update", methods=["POST"])
@role_required("Admin")
def admin_restaurant_update(rid: int):
    try:
        r = Restaurant.query.get_or_404(rid)
        r.name = request.form["name"].strip()
        r.address = request.form["address"].strip()
        r.status = request.form.get("status", "Active")
        r.owner_id = int(request.form["owner_id"]) if request.form.get("owner_id") else None
        db.session.commit()
        flash("Restaurant updated.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("admin_restaurants"))


@app.route("/admin/restaurants/<int:rid>/delete", methods=["POST"])
@role_required("Admin")
def admin_restaurant_delete(rid: int):
    try:
        r = Restaurant.query.get_or_404(rid)
        db.session.delete(r)
        db.session.commit()
        flash("Restaurant deleted.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(f"Cannot delete (maybe menu/orders exist): {e}", "error")
    return redirect(url_for("admin_restaurants"))


@app.route("/admin/agents", methods=["GET", "POST"])
@role_required("Admin")
def admin_agents():
    if request.method == "POST":
        try:
            u = User(
                full_name=request.form["full_name"].strip(),
                email=request.form["email"].strip().lower(),
                phone_number=request.form["phone_number"].strip(),
                type="Delivery Agent",
                password_hash=generate_password_hash(request.form["password"]),
                address=(request.form.get("address") or "").strip() or None
            )
            db.session.add(u)
            db.session.commit()
            flash("Delivery agent created.", "ok")
        except Exception as e:
            db.session.rollback()
            flash(str(e), "error")
        return redirect(url_for("admin_agents"))

    agents = User.query.filter_by(type="Delivery Agent").order_by(User.user_id.desc()).all()
    return render_template("admin/agents.html", agents=agents)


@app.route("/admin/agents/<int:uid>/update", methods=["POST"])
@role_required("Admin")
def admin_agent_update(uid: int):
    try:
        u = User.query.get_or_404(uid)
        if u.type != "Delivery Agent":
            abort(403)
        u.full_name = request.form["full_name"].strip()
        u.phone_number = request.form["phone_number"].strip()
        u.address = (request.form.get("address") or "").strip() or None
        if (request.form.get("password") or "").strip():
            u.password_hash = generate_password_hash(request.form["password"])
        db.session.commit()
        flash("Agent updated.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("admin_agents"))


@app.route("/admin/agents/<int:uid>/delete", methods=["POST"])
@role_required("Admin")
def admin_agent_delete(uid: int):
    try:
        u = User.query.get_or_404(uid)
        if u.type != "Delivery Agent":
            abort(403)
        db.session.delete(u)
        db.session.commit()
        flash("Agent deleted.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(f"Cannot delete (maybe assigned deliveries exist): {e}", "error")
    return redirect(url_for("admin_agents"))


@app.route("/admin/orders")
@role_required("Admin")
def admin_orders():
    status = (request.args.get("status") or "").strip()
    q = Order.query
    if status in ("Placed", "Accepted", "Preparing", "Out for Delivery", "Delivered", "Cancelled"):
        q = q.filter_by(status=status)

    orders = q.order_by(Order.order_id.desc()).limit(50).all()
    agents = User.query.filter_by(type="Delivery Agent").order_by(User.user_id.desc()).all()
    return render_template("admin/orders.html", orders=orders, agents=agents, status=status)


@app.route("/admin/orders/<int:oid>/assign", methods=["POST"])
@role_required("Admin")
def admin_assign_delivery(oid: int):
    try:
        order = Order.query.get_or_404(oid)
        agent_id = int(request.form["delivery_agent_id"])
        exp_raw = (request.form.get("expected_drop_at") or "").strip()

        agent = User.query.get_or_404(agent_id)
        if agent.type != "Delivery Agent":
            raise ValueError("Selected user is not a Delivery Agent.")

        expected = None
        if exp_raw:
            expected = datetime.strptime(exp_raw, "%Y-%m-%d %H:%M:%S")

        da = DeliveryAssignment.query.filter_by(order_id=order.order_id).first()
        if not da:
            da = DeliveryAssignment(order_id=order.order_id, delivery_agent_id=agent_id, expected_drop_at=expected)
            db.session.add(da)
        else:
            da.delivery_agent_id = agent_id
            da.expected_drop_at = expected

        db.session.commit()
        flash("Delivery assigned/updated.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("admin_orders"))


# -------------------- CUSTOMER --------------------
def get_cart():
    return session.get("cart", {"restaurant_id": None, "items": {}})


def save_cart(cart):
    session["cart"] = cart


@app.route("/customer/restaurants")
@role_required("Customer")
def customer_restaurants():
    active_only = (request.args.get("active_only") or "1") == "1"
    q = (request.args.get("q") or "").strip()

    query = Restaurant.query
    if active_only:
        query = query.filter_by(status="Active")
    if q:
        query = query.filter(Restaurant.name.like(f"%{q}%"))

    restaurants = query.order_by(Restaurant.restaurant_id.desc()).all()
    return render_template("customer/restaurants.html", restaurants=restaurants, q=q, active_only=active_only)


@app.route("/customer/restaurant/<int:rid>")
@role_required("Customer")
def customer_restaurant_menu(rid: int):
    r = Restaurant.query.get_or_404(rid)
    if r.status != "Active":
        flash("This restaurant is currently inactive.", "error")
        return redirect(url_for("customer_restaurants"))

    category = (request.args.get("category") or "").strip()  # Food/Drink
    only_available = (request.args.get("only_available") or "1") == "1"
    q = (request.args.get("q") or "").strip()

    query = MenuItem.query.filter_by(restaurant_id=r.restaurant_id)
    if only_available:
        query = query.filter_by(availability=True)
    if category in ("Food", "Drink"):
        query = query.filter_by(category=category)
    if q:
        query = query.filter(MenuItem.name.like(f"%{q}%"))

    items = query.order_by(MenuItem.menu_id.desc()).all()
    cart = get_cart()
    return render_template("customer/restaurant_menu.html", r=r, items=items, cart=cart, category=category, only_available=only_available, q=q)


@app.route("/customer/cart")
@role_required("Customer")
def customer_cart():
    cart = get_cart()
    rest = Restaurant.query.get(cart["restaurant_id"]) if cart["restaurant_id"] else None
    lines = []
    total = Decimal("0.00")

    if rest:
        for mid_str, qty in cart["items"].items():
            mi = MenuItem.query.get(int(mid_str))
            if not mi:
                continue
            line_total = Decimal(str(mi.price)) * Decimal(str(qty))
            total += line_total
            lines.append((mi, qty, line_total))

    return render_template("customer/cart.html", cart=cart, rest=rest, lines=lines, total=total)


@app.route("/customer/cart/add", methods=["POST"])
@role_required("Customer")
def customer_cart_add():
    try:
        rid = int(request.form["restaurant_id"])
        mid = int(request.form["menu_id"])
        qty = int(request.form.get("qty", "1"))

        r = Restaurant.query.get_or_404(rid)
        if r.status != "Active":
            raise ValueError("Restaurant inactive.")

        mi = MenuItem.query.get_or_404(mid)
        if mi.restaurant_id != rid:
            raise ValueError("Invalid item for this restaurant.")
        if not mi.availability:
            raise ValueError("Item unavailable.")
        if qty <= 0:
            raise ValueError("Qty must be >= 1")

        cart = get_cart()

        # One-restaurant cart rule
        if cart["restaurant_id"] and cart["restaurant_id"] != rid:
            cart = {"restaurant_id": rid, "items": {}}

        cart["restaurant_id"] = rid
        cart["items"][str(mid)] = cart["items"].get(str(mid), 0) + qty
        save_cart(cart)

        flash("Added to cart.", "ok")
    except Exception as e:
        flash(str(e), "error")

    return redirect(url_for("customer_restaurant_menu", rid=rid))


@app.route("/customer/cart/update", methods=["POST"])
@role_required("Customer")
def customer_cart_update():
    cart = get_cart()
    new_items = {}
    for k, v in request.form.items():
        if not k.startswith("qty_"):
            continue
        mid = k.replace("qty_", "").strip()
        try:
            qty = int(v)
        except Exception:
            qty = 0
        if qty > 0:
            new_items[mid] = qty
    cart["items"] = new_items
    if not cart["items"]:
        cart = {"restaurant_id": None, "items": {}}
    save_cart(cart)
    flash("Cart updated.", "ok")
    return redirect(url_for("customer_cart"))


@app.route("/customer/cart/clear", methods=["POST"])
@role_required("Customer")
def customer_cart_clear():
    session["cart"] = {"restaurant_id": None, "items": {}}
    flash("Cart cleared.", "ok")
    return redirect(url_for("customer_cart"))


@app.route("/customer/checkout", methods=["POST"])
@role_required("Customer")
def customer_checkout():
    try:
        cart = get_cart()
        if not cart["restaurant_id"] or not cart["items"]:
            raise ValueError("Cart is empty.")

        r = Restaurant.query.get_or_404(cart["restaurant_id"])
        if r.status != "Active":
            raise ValueError("Restaurant inactive.")

        order = Order(
            user_id=g.user.user_id,
            restaurant_id=r.restaurant_id,
            status="Placed",
            payment_method=request.form["payment_method"],
            delivery_instructions=(request.form.get("delivery_instructions") or "").strip() or None,
        )
        db.session.add(order)
        db.session.flush()

        added = 0
        for mid_str, qty in cart["items"].items():
            mi = MenuItem.query.get(int(mid_str))
            if not mi or mi.restaurant_id != r.restaurant_id or not mi.availability:
                continue
            db.session.add(OrderItem(
                order_id=order.order_id,
                menu_item_id=mi.menu_id,
                quantity=int(qty),
                price_at_purchase=mi.price,
            ))
            added += 1

        if added == 0:
            raise ValueError("No valid items to checkout.")

        log_history(order.order_id, "Placed", g.user.user_id, "Order placed by customer")
        db.session.commit()

        session["cart"] = {"restaurant_id": None, "items": {}}
        flash(f"Order placed! Order ID: {order.order_id}", "ok")
        return redirect(url_for("customer_track", oid=order.order_id))

    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("customer_cart"))


@app.route("/customer/orders")
@role_required("Customer")
def customer_orders():
    orders = Order.query.filter_by(user_id=g.user.user_id).order_by(Order.order_id.desc()).all()
    return render_template("customer/orders.html", orders=orders, calc_order_total=calc_order_total)


@app.route("/customer/order/<int:oid>")
@role_required("Customer")
def customer_track(oid: int):
    order = Order.query.get_or_404(oid)
    if order.user_id != g.user.user_id:
        abort(403)

    total = calc_order_total(order)
    eta_label, eta_detail = eta_for_order(order)

    last_loc = None
    if order.delivery and order.delivery.locations:
        last_loc = sorted(order.delivery.locations, key=lambda x: x.created_at)[-1]

    history = OrderStatusHistory.query.filter_by(order_id=order.order_id).order_by(OrderStatusHistory.created_at.asc()).all()

    return render_template(
        "customer/track.html",
        order=order,
        total=total,
        eta_label=eta_label,
        eta_detail=eta_detail,
        last_loc=last_loc,
        history=history,
    )


# -------------------- RESTAURANT OWNER --------------------
def owner_restaurants() -> list[Restaurant]:
    return Restaurant.query.filter_by(owner_id=g.user.user_id).order_by(Restaurant.restaurant_id.desc()).all()


@app.route("/owner")
@role_required("Restaurant Owner")
def owner_dashboard():
    rests = owner_restaurants()
    rest_ids = [r.restaurant_id for r in rests]
    orders = []
    if rest_ids:
        orders = Order.query.filter(Order.restaurant_id.in_(rest_ids)).order_by(Order.order_id.desc()).limit(20).all()
    return render_template("owner/dashboard.html", rests=rests, orders=orders, calc_order_total=calc_order_total)


@app.route("/owner/menu", methods=["GET", "POST"])
@role_required("Restaurant Owner")
def owner_menu():
    rests = owner_restaurants()
    if not rests:
        flash("No restaurant assigned to you. Ask admin to link owner to restaurant.", "error")
        return render_template("owner/menu.html", rests=[], active_rest=None, items=[])

    rid = int(request.args.get("rid", rests[0].restaurant_id))
    active_rest = Restaurant.query.get_or_404(rid)
    if active_rest.owner_id != g.user.user_id:
        abort(403)

    if request.method == "POST":
        try:
            mi = MenuItem(
                restaurant_id=active_rest.restaurant_id,
                name=request.form["name"].strip(),
                price=Decimal(request.form["price"]).quantize(Decimal("0.01")),
                category=request.form.get("category") or None,
                availability=True if request.form.get("availability") == "on" else False,
            )
            db.session.add(mi)
            db.session.commit()
            flash("Menu item added.", "ok")
        except Exception as e:
            db.session.rollback()
            flash(str(e), "error")
        return redirect(url_for("owner_menu", rid=active_rest.restaurant_id))

    items = MenuItem.query.filter_by(restaurant_id=active_rest.restaurant_id).order_by(MenuItem.menu_id.desc()).all()
    return render_template("owner/menu.html", rests=rests, active_rest=active_rest, items=items)


@app.route("/owner/menu/<int:mid>/update", methods=["POST"])
@role_required("Restaurant Owner")
def owner_menu_update(mid: int):
    mi = MenuItem.query.get_or_404(mid)
    r = Restaurant.query.get_or_404(mi.restaurant_id)
    if r.owner_id != g.user.user_id:
        abort(403)

    try:
        mi.name = request.form["name"].strip()
        mi.price = Decimal(request.form["price"]).quantize(Decimal("0.01"))
        mi.category = request.form.get("category") or None
        mi.availability = True if request.form.get("availability") == "on" else False
        db.session.commit()
        flash("Menu updated.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")

    return redirect(url_for("owner_menu", rid=r.restaurant_id))


@app.route("/owner/menu/<int:mid>/delete", methods=["POST"])
@role_required("Restaurant Owner")
def owner_menu_delete(mid: int):
    mi = MenuItem.query.get_or_404(mid)
    r = Restaurant.query.get_or_404(mi.restaurant_id)
    if r.owner_id != g.user.user_id:
        abort(403)

    try:
        db.session.delete(mi)
        db.session.commit()
        flash("Item deleted.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")

    return redirect(url_for("owner_menu", rid=r.restaurant_id))


@app.route("/owner/orders")
@role_required("Restaurant Owner")
def owner_orders():
    rests = owner_restaurants()
    rest_ids = [r.restaurant_id for r in rests]
    orders = []
    if rest_ids:
        orders = Order.query.filter(Order.restaurant_id.in_(rest_ids)).order_by(Order.order_id.desc()).limit(100).all()
    return render_template("owner/orders.html", rests=rests, orders=orders, calc_order_total=calc_order_total)


@app.route("/owner/orders/<int:oid>/status", methods=["POST"])
@role_required("Restaurant Owner")
def owner_update_order_status(oid: int):
    order = Order.query.get_or_404(oid)
    r = Restaurant.query.get_or_404(order.restaurant_id)
    if r.owner_id != g.user.user_id:
        abort(403)

    new_status = request.form["status"].strip()
    allowed = {"Accepted", "Preparing"}
    if new_status not in allowed:
        abort(400)

    try:
        order.status = new_status
        if new_status == "Accepted":
            order.accepted_at = now_utc()
        if new_status == "Preparing":
            order.preparing_at = now_utc()

        log_history(order.order_id, new_status, g.user.user_id, "Updated by restaurant owner")
        db.session.commit()
        flash("Order status updated.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")

    return redirect(url_for("owner_orders"))


# -------------------- DELIVERY AGENT --------------------
@app.route("/agent")
@role_required("Delivery Agent")
def agent_dashboard():
    deliveries = DeliveryAssignment.query.filter_by(delivery_agent_id=g.user.user_id).order_by(DeliveryAssignment.delivery_id.desc()).limit(50).all()
    return render_template("agent/dashboard.html", deliveries=deliveries, calc_order_total=calc_order_total)


@app.route("/agent/order/<int:oid>")
@role_required("Delivery Agent")
def agent_order(oid: int):
    order = Order.query.get_or_404(oid)
    if not order.delivery or order.delivery.delivery_agent_id != g.user.user_id:
        abort(403)

    total = calc_order_total(order)
    history = OrderStatusHistory.query.filter_by(order_id=order.order_id).order_by(OrderStatusHistory.created_at.asc()).all()
    last_loc = None
    if order.delivery.locations:
        last_loc = sorted(order.delivery.locations, key=lambda x: x.created_at)[-1]

    return render_template("agent/order.html", order=order, total=total, history=history, last_loc=last_loc)


@app.route("/agent/order/<int:oid>/update", methods=["POST"])
@role_required("Delivery Agent")
def agent_update_delivery(oid: int):
    order = Order.query.get_or_404(oid)
    if not order.delivery or order.delivery.delivery_agent_id != g.user.user_id:
        abort(403)

    action = request.form["action"].strip()
    try:
        if action == "pickup":
            order.delivery.status = "Pickup"
            order.delivery.pickup_at = now_utc()
            order.status = "Out for Delivery"
            order.out_for_delivery_at = now_utc()
            log_history(order.order_id, "Out for Delivery", g.user.user_id, "Picked up by agent")

        elif action == "drop":
            order.delivery.status = "Dropped"
            order.delivery.dropped_at = now_utc()
            order.status = "Delivered"
            order.delivered_at = now_utc()
            log_history(order.order_id, "Delivered", g.user.user_id, "Delivered by agent")

        else:
            abort(400)

        db.session.commit()
        flash("Updated.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")

    return redirect(url_for("agent_order", oid=order.order_id))


@app.route("/agent/delivery/<int:delivery_id>/location", methods=["POST"])
@role_required("Delivery Agent")
def agent_update_location(delivery_id: int):
    d = DeliveryAssignment.query.get_or_404(delivery_id)
    if d.delivery_agent_id != g.user.user_id:
        abort(403)

    try:
        lat = Decimal(request.form["lat"])
        lng = Decimal(request.form["lng"])
        note = (request.form.get("note") or "").strip() or None

        db.session.add(DeliveryLocation(delivery_id=d.delivery_id, lat=lat, lng=lng, note=note))
        db.session.commit()
        flash("Location updated.", "ok")
    except Exception as e:
        db.session.rollback()
        flash(str(e), "error")

    return redirect(url_for("agent_order", oid=d.order_id))


# -------------------- INIT + RUN --------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_if_empty()
        print("DB ready + seed ensured.")

    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)