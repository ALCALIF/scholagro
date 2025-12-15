from flask import Blueprint, redirect, url_for, request, render_template, flash, session
from flask_login import login_required, current_user
from ...extensions import db, csrf
from ...models import CartItem, Product, SavedItem
from ...extensions import limiter

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")


@cart_bp.route("/")
@login_required
def view_cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    # Use db.session.get to avoid SQLAlchemy 2.x deprecation warnings
    total = sum(i.quantity * float(db.session.get(Product, i.product_id).price) for i in items)
    return render_template("cart.html", items=items, total=total)


@cart_bp.route("/mini")
def mini_cart():
    """
    Public mini cart API endpoint. If the user is not authenticated, return an empty cart structure
    instead of redirecting to login. This enables client-side widgets to poll this endpoint without
    forcing a login redirect.
    """
    if not getattr(current_user, 'is_authenticated', False):
        # Build from session cart
        cart = session.get('cart', {}) or {}
        data_items = []
        subtotal = 0.0
        for pid_str, qty in cart.items():
            try:
                pid = int(pid_str)
                qty = int(qty)
            except Exception:
                continue
            p = db.session.get(Product, pid)
            if not p:
                continue
            line_total = qty * float(p.price)
            subtotal += line_total
            data_items.append({
                "item_id": None,
                "product_id": p.id,
                "name": p.name,
                "slug": p.slug,
                "price": float(p.price),
                "quantity": int(qty),
                "image_url": getattr(p, 'image_url', None),
                "line_total": round(line_total, 2),
            })
        count = sum(int(v or 0) for v in cart.values())
        return {
            "ok": True,
            "items": data_items,
            "subtotal": round(subtotal, 2),
            "count": int(count),
        }
    from sqlalchemy import func
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    data_items = []
    subtotal = 0.0
    for it in items:
        p = db.session.get(Product, it.product_id)
        if not p:
            continue
        line_total = (it.quantity or 0) * float(p.price)
        subtotal += line_total
        data_items.append({
            "item_id": it.id,
            "product_id": p.id,
            "name": p.name,
            "slug": p.slug,
            "price": float(p.price),
            "quantity": int(it.quantity or 0),
            "image_url": getattr(p, 'image_url', None),
            "line_total": round(line_total, 2),
        })
    count = (request.args.get('count_only') == '1') and 0 or len(items)
    try:
        count = int(db.session.query(func.coalesce(func.sum(CartItem.quantity), 0)).filter_by(user_id=current_user.id).scalar() or 0)
    except Exception:
        count = len(items)
    return {
        "ok": True,
        "items": data_items,
        "subtotal": round(subtotal, 2),
        "count": int(count),
    }


@cart_bp.route("/add/<int:product_id>")
@limiter.limit("30 per minute")
def add(product_id):
    if getattr(current_user, 'is_authenticated', False):
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if item:
            item.quantity += 1
        else:
            item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
            db.session.add(item)
        db.session.commit()
    else:
        cart = session.get('cart', {}) or {}
        cart[str(product_id)] = int(cart.get(str(product_id), 0)) + 1
        session['cart'] = cart
    flash("Added to cart", "success")
    return redirect(request.referrer or url_for("shop.shop"))


@cart_bp.route("/remove/<int:item_id>")
@login_required
@limiter.limit("60 per minute")
def remove(item_id):
    item = db.session.get(CartItem, item_id)
    if not item:
        from flask import abort
        abort(404)
    if item.user_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for("cart.view_cart"))
    db.session.delete(item)
    db.session.commit()
    flash("Removed from cart", "info")
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/add", methods=["POST"])
@csrf.exempt
@limiter.limit("30 per minute")
def add_json():
    pid = request.json.get("product_id") if request.is_json else request.form.get("product_id")
    try:
        pid = int(pid)
    except Exception:
        return {"ok": False, "message": "Invalid product"}, 400
    product = db.session.get(Product, pid)
    if not product:
        return {"ok": False, "message": "Product not found"}, 404
    if getattr(current_user, 'is_authenticated', False):
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
        if item:
            item.quantity += 1
        else:
            item = CartItem(user_id=current_user.id, product_id=pid, quantity=1)
            db.session.add(item)
        db.session.commit()
        from sqlalchemy import func
        cart_count = db.session.query(func.coalesce(func.sum(CartItem.quantity), 0)).filter_by(user_id=current_user.id).scalar() or 0
        return {"ok": True, "message": f"Added {product.name}", "cart_count": int(cart_count)}
    else:
        cart = session.get('cart', {}) or {}
        cart[str(pid)] = int(cart.get(str(pid), 0)) + 1
        session['cart'] = cart
        count = sum(int(v or 0) for v in cart.values())
        return {"ok": True, "message": f"Added {product.name}", "cart_count": int(count)}


@cart_bp.route("/update", methods=["POST"])
@csrf.exempt
@limiter.limit("60 per minute")
def update_quantity():
    data = request.get_json(silent=True) or {}
    try:
        qty = int(data.get("quantity"))
    except Exception:
        return {"ok": False, "message": "Invalid input"}, 400
    if getattr(current_user, 'is_authenticated', False):
        try:
            item_id = int(data.get("item_id"))
        except Exception:
            return {"ok": False, "message": "Invalid input"}, 400
        item = db.session.get(CartItem, item_id)
        if not item or item.user_id != current_user.id:
            return {"ok": False, "message": "Item not found"}, 404
        if qty <= 0:
            db.session.delete(item)
            db.session.commit()
        else:
            item.quantity = min(99, qty)
            db.session.commit()
        # Recalculate totals
        from sqlalchemy import func
        item_subtotal = 0.0
        if qty > 0:
            p = db.session.get(Product, item.product_id)
            item_subtotal = (item.quantity or 0) * float(p.price if p else 0)
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        cart_subtotal = sum((ci.quantity or 0) * float(db.session.get(Product, ci.product_id).price) for ci in cart_items)
        count = db.session.query(func.coalesce(func.sum(CartItem.quantity), 0)).filter_by(user_id=current_user.id).scalar() or 0
        return {
            "ok": True,
            "item_id": item_id,
            "quantity": max(0, qty),
            "item_subtotal": round(item_subtotal, 2),
            "cart_subtotal": round(cart_subtotal, 2),
            "cart_count": int(count),
            "removed": qty <= 0,
        }
    else:
        # Guest cart update via product_id
        try:
            pid = int(data.get("product_id"))
        except Exception:
            return {"ok": False, "message": "Invalid input"}, 400
        cart = session.get('cart', {}) or {}
        if qty <= 0:
            cart.pop(str(pid), None)
        else:
            cart[str(pid)] = min(99, qty)
        session['cart'] = cart
        # Totals
        cart_items = []
        subtotal = 0.0
        for k, v in cart.items():
            try:
                p = db.session.get(Product, int(k))
                line = int(v) * float(p.price if p else 0)
                subtotal += line
                if int(k) == pid:
                    item_subtotal = line
            except Exception:
                pass
        count = sum(int(v or 0) for v in cart.values())
        return {
            "ok": True,
            "product_id": pid,
            "quantity": max(0, qty),
            "item_subtotal": round(locals().get('item_subtotal', 0.0), 2),
            "cart_subtotal": round(subtotal, 2),
            "cart_count": int(count),
            "removed": qty <= 0,
        }


@cart_bp.route("/save", methods=["POST"])
@login_required
@csrf.exempt
def save_for_later():
    data = request.get_json(silent=True) or {}
    try:
        item_id = int(data.get("item_id"))
    except Exception:
        return {"ok": False, "message": "Invalid input"}, 400
    item = db.session.get(CartItem, item_id)
    if not item or item.user_id != current_user.id:
        return {"ok": False, "message": "Item not found"}, 404
    # Create saved item if not exists
    exists = SavedItem.query.filter_by(user_id=current_user.id, product_id=item.product_id).first()
    if not exists:
        db.session.add(SavedItem(user_id=current_user.id, product_id=item.product_id))
    # Remove from cart
    db.session.delete(item)
    db.session.commit()
    from sqlalchemy import func
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    cart_subtotal = sum((ci.quantity or 0) * float(db.session.get(Product, ci.product_id).price) for ci in cart_items)
    count = db.session.query(func.coalesce(func.sum(CartItem.quantity), 0)).filter_by(user_id=current_user.id).scalar() or 0
    return {"ok": True, "message": "Saved for later", "cart_subtotal": round(cart_subtotal, 2), "cart_count": int(count)}
