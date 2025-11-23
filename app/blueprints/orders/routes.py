from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from ...extensions import db
from ...utils.email import send_email, send_email_html
from flask import render_template
from ...models import CartItem, Order, OrderItem, DeliveryAddress, Product, DeliveryZone, Coupon, OrderStatusLog
from datetime import datetime

orders_bp = Blueprint("orders", __name__, url_prefix="/orders")


@orders_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash("Your cart is empty", "warning")
        return redirect(url_for("shop.shop"))
    addresses = DeliveryAddress.query.filter_by(user_id=current_user.id).all()
    zones = DeliveryZone.query.all()
    if request.method == "POST":
        address_id = request.form.get("address_id")
        slot = request.form.get("slot")
        zone_id = request.form.get("zone_id", type=int)
        coupon_code = request.form.get("coupon_code", type=str)
        instructions = request.form.get("instructions")

        # Validate stock
        for i in items:
            p = Product.query.get(i.product_id)
            if not p or p.stock is not None and int(p.stock) < int(i.quantity):
                flash(f"Insufficient stock for {p.name if p else 'item'}", "danger")
                return redirect(url_for("cart.view_cart"))

        order = Order(
            user_id=current_user.id,
            status="pending",
            delivery_time_slot=slot,
            delivery_zone_id=zone_id,
            instructions=instructions,
        )
        db.session.add(order)
        db.session.flush()
        total = 0
        for i in items:
            p = Product.query.get(i.product_id)
            oi = OrderItem(order_id=order.id, product_id=p.id, product_name=p.name, quantity=i.quantity, unit_price=p.price)
            db.session.add(oi)
            total += i.quantity * float(p.price)
            # decrement stock
            if p.stock is not None:
                p.stock = max(0, int(p.stock) - int(i.quantity))
        fee = 0
        if zone_id:
            z = DeliveryZone.query.get(zone_id)
            fee = float(z.fee) if z else 0
        discount_amt = 0
        if coupon_code:
            c = Coupon.query.filter(
                Coupon.code.ilike(coupon_code.strip()),
                Coupon.is_active.is_(True),
            ).first()
            if c:
                # Validate expiry/min value/usage
                if c.expires_at and c.expires_at < datetime.utcnow():
                    flash("Coupon has expired", "warning")
                elif c.min_order_value and float(total) < float(c.min_order_value):
                    flash("Order total does not meet coupon minimum", "warning")
                elif c.max_usage and c.usage_count and int(c.usage_count) >= int(c.max_usage):
                    flash("Coupon usage limit reached", "warning")
                else:
                    if c.discount_amount and float(c.discount_amount) > 0:
                        discount_amt = float(c.discount_amount)
                    elif c.discount_percent and int(c.discount_percent) > 0:
                        discount_amt = round(float(total) * (int(c.discount_percent) / 100.0), 2)
                    order.coupon_code = c.code
                    order.discount_amount = discount_amt
        order.delivery_fee = fee
        order.total_amount = max(0, total + fee - discount_amt)
        order.address_id = int(address_id) if address_id else None
        db.session.query(CartItem).filter_by(user_id=current_user.id).delete()
        # increment coupon usage if applied
        if order.coupon_code:
            try:
                c.usage_count = (c.usage_count or 0) + 1
            except Exception:
                pass
        # initial status log
        try:
            db.session.add(OrderStatusLog(order_id=order.id, status="placed", notes="Order created"))
        except Exception:
            pass
        db.session.commit()
        try:
            html = render_template('emails/order_created.html', order=order, user=current_user)
            send_email_html(to=current_user.email, subject=f"Order #{order.id} placed", html=html)
        except Exception:
            pass
        flash("Order created. Proceed to payment.", "success")
        return redirect(url_for("payments.start_mpesa", order_id=order.id))
    # Compute subtotal for display and client-side calculations
    subtotal = 0.0
    for i in items:
        try:
            p = Product.query.get(i.product_id)
            subtotal += (i.quantity or 0) * float(p.price if p else 0)
        except Exception:
            pass
    return render_template("checkout.html", items=items, addresses=addresses, zones=zones, total=subtotal)


@orders_bp.route("/apply-coupon", methods=["POST"])
@login_required
def apply_coupon():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    subtotal = float(data.get("subtotal") or 0)
    if not code:
        return jsonify({"ok": False, "message": "Enter a coupon code"}), 400
    c = Coupon.query.filter(Coupon.code.ilike(code), Coupon.is_active.is_(True)).first()
    if not c:
        return jsonify({"ok": False, "message": "Invalid coupon"}), 404
    # validations
    if c.expires_at and c.expires_at < datetime.utcnow():
        return jsonify({"ok": False, "message": "Coupon expired"}), 400
    if c.min_order_value and subtotal < float(c.min_order_value):
        return jsonify({"ok": False, "message": "Order does not meet minimum"}), 400
    if c.max_usage and c.usage_count and int(c.usage_count) >= int(c.max_usage):
        return jsonify({"ok": False, "message": "Usage limit reached"}), 400
    discount = 0.0
    if c.discount_amount and float(c.discount_amount) > 0:
        discount = float(c.discount_amount)
    elif c.discount_percent and int(c.discount_percent) > 0:
        discount = round(subtotal * (int(c.discount_percent) / 100.0), 2)
    return jsonify({
        "ok": True,
        "code": c.code,
        "discount": discount,
        "message": "Coupon applied",
    })


@orders_bp.route("")
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("orders.html", orders=orders)


@orders_bp.route("/<int:order_id>")
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash("Not found", "danger")
        return redirect(url_for("orders.my_orders"))
    # Simple 5-minute cancel window
    can_cancel = order.status in ("pending", "packed") and (datetime.utcnow() - order.created_at).total_seconds() <= 300
    logs = OrderStatusLog.query.filter_by(order_id=order.id).order_by(OrderStatusLog.created_at.asc()).all()
    return render_template("order_detail.html", order=order, can_cancel=can_cancel, logs=logs)


@orders_bp.route("/<int:order_id>/cancel")
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash("Not found", "danger")
        return redirect(url_for("orders.my_orders"))
    # Disallow cancel after payment
    if order.payment and order.payment.status == 'paid':
        flash("This order has been paid and cannot be cancelled.", "warning")
        return redirect(url_for("orders.order_detail", order_id=order.id))
    # Allow cancel within 5 minutes for pending/packed
    if order.status not in ("pending", "packed"):
        flash("Order cannot be cancelled at this stage", "warning")
        return redirect(url_for("orders.order_detail", order_id=order.id))
    if (datetime.utcnow() - order.created_at).total_seconds() > 300:
        flash("Cancel window has passed", "warning")
        return redirect(url_for("orders.order_detail", order_id=order.id))
    order.status = "cancelled"
    try:
        db.session.add(OrderStatusLog(order_id=order.id, status="cancelled", notes="Cancelled by user"))
    except Exception:
        pass
    db.session.commit()
    flash("Order cancelled", "success")
    return redirect(url_for("orders.my_orders"))
