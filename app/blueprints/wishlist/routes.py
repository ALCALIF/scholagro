from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from ...extensions import db, csrf
from ...models import WishlistItem, Product

wishlist_bp = Blueprint("wishlist", __name__, url_prefix="/wishlist")


@wishlist_bp.route("/")
@login_required
def view_wishlist():
    items = WishlistItem.query.filter_by(user_id=current_user.id).all()
    return render_template("wishlist.html", items=items)


@wishlist_bp.route("/toggle", methods=["POST"])
@login_required
@csrf.exempt
def toggle():
    pid = request.json.get("product_id") if request.is_json else request.form.get("product_id")
    try:
        pid = int(pid)
    except Exception:
        return {"ok": False, "message": "Invalid product"}, 400
    product = Product.query.get(pid)
    if not product:
        return {"ok": False, "message": "Product not found"}, 404
    item = WishlistItem.query.filter_by(user_id=current_user.id, product_id=pid).first()
    added = False
    if item:
        db.session.delete(item)
    else:
        db.session.add(WishlistItem(user_id=current_user.id, product_id=pid))
        added = True
    db.session.commit()
    return {"ok": True, "added": added}
