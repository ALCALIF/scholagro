from flask import Blueprint, redirect, url_for, request, render_template, flash
from flask_login import login_required, current_user
from ...extensions import db, csrf
from ...models import CartItem, Product, SavedItem

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")


@cart_bp.route("/")
@login_required
def view_cart():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(i.quantity * float(Product.query.get(i.product_id).price) for i in items)
    return render_template("cart.html", items=items, total=total)


@cart_bp.route("/add/<int:product_id>")
@login_required
def add(product_id):
    item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=current_user.id, product_id=product_id, quantity=1)
        db.session.add(item)
    db.session.commit()
    flash("Added to cart", "success")
    return redirect(request.referrer or url_for("shop.shop"))


@cart_bp.route("/remove/<int:item_id>")
@login_required
def remove(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for("cart.view_cart"))
    db.session.delete(item)
    db.session.commit()
    flash("Removed from cart", "info")
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/add", methods=["POST"])
@login_required
@csrf.exempt
def add_json():
    pid = request.json.get("product_id") if request.is_json else request.form.get("product_id")
    try:
        pid = int(pid)
    except Exception:
        return {"ok": False, "message": "Invalid product"}, 400
    product = Product.query.get(pid)
    if not product:
        return {"ok": False, "message": "Product not found"}, 404
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


@cart_bp.route("/update", methods=["POST"])
@login_required
@csrf.exempt
def update_quantity():
    data = request.get_json(silent=True) or {}
    try:
        item_id = int(data.get("item_id"))
        qty = int(data.get("quantity"))
    except Exception:
        return {"ok": False, "message": "Invalid input"}, 400
    item = CartItem.query.get(item_id)
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
    # Ensure product price fetch is safe even if item deleted
    item_subtotal = 0.0
    if qty > 0:
        p = Product.query.get(item.product_id)
        item_subtotal = (item.quantity or 0) * float(p.price if p else 0)
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    cart_subtotal = sum((ci.quantity or 0) * float(Product.query.get(ci.product_id).price) for ci in cart_items)
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


@cart_bp.route("/save", methods=["POST"])
@login_required
@csrf.exempt
def save_for_later():
    data = request.get_json(silent=True) or {}
    try:
        item_id = int(data.get("item_id"))
    except Exception:
        return {"ok": False, "message": "Invalid input"}, 400
    item = CartItem.query.get(item_id)
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
    cart_subtotal = sum((ci.quantity or 0) * float(Product.query.get(ci.product_id).price) for ci in cart_items)
    count = db.session.query(func.coalesce(func.sum(CartItem.quantity), 0)).filter_by(user_id=current_user.id).scalar() or 0
    return {"ok": True, "message": "Saved for later", "cart_subtotal": round(cart_subtotal, 2), "cart_count": int(count)}
