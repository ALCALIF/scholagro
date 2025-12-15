from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from ...extensions import db
from ...models import DeliveryAddress, SavedItem, Product
from ...models import Notification

account_bp = Blueprint("account", __name__, url_prefix="/account")


@account_bp.route("/addresses", methods=["GET", "POST"])
@login_required
def addresses():
    if request.method == "POST":
        line1 = request.form.get("line1")
        city = request.form.get("city")
        zone = request.form.get("zone")
        postal_code = request.form.get("postal_code")
        if not line1:
            flash("Line 1 is required", "danger")
        else:
            addr = DeliveryAddress(user_id=current_user.id, line1=line1, city=city, zone=zone, postal_code=postal_code)
            db.session.add(addr)
            db.session.commit()
            flash("Address added", "success")
            return redirect(url_for("account.addresses"))
    addrs = DeliveryAddress.query.filter_by(user_id=current_user.id).all()
    return render_template("account/addresses.html", addresses=addrs)


@account_bp.route("/addresses/<int:addr_id>/delete", methods=["POST"])
@login_required
def delete_address(addr_id):
    addr = db.session.get(DeliveryAddress, addr_id)
    if not addr:
        abort(404)
    if addr.user_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for("account.addresses"))
    db.session.delete(addr)
    db.session.commit()
    flash("Address deleted", "info")
    return redirect(url_for("account.addresses"))


@account_bp.route("/addresses/<int:addr_id>/default", methods=["POST"])
@login_required
def set_default_address(addr_id):
    addr = db.session.get(DeliveryAddress, addr_id)
    if not addr:
        abort(404)
    if addr.user_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for("account.addresses"))
    # unset other defaults
    DeliveryAddress.query.filter_by(user_id=current_user.id, is_default=True).update({DeliveryAddress.is_default: False})
    addr.is_default = True
    db.session.commit()
    flash("Default address updated", "success")
    return redirect(url_for("account.addresses"))


@account_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        current_user.name = name
        current_user.phone = phone
        db.session.commit()
        flash("Profile updated", "success")
        return redirect(url_for("account.profile"))
    return render_template("account/profile.html")


@account_bp.route("/saved")
@login_required
def saved_items():
    items = SavedItem.query.filter_by(user_id=current_user.id).all()
    # Attach product info if needed (relationship already present)
    return render_template("account/saved.html", items=items)


@account_bp.route('/notifications/json')
@login_required
def notifications_json():
    items = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(10).all()
    return {"ok": True, "notifications": [{"id": n.id, "title": n.title, "message": n.message, "type": n.type, "created_at": n.created_at.isoformat() if n.created_at else None} for n in items]}


@account_bp.route('/notifications/<int:not_id>/read', methods=['POST'])
@login_required
def mark_notification_read(not_id):
    n = db.session.get(Notification, not_id)
    if not n:
        abort(404)
    if n.user_id != current_user.id:
        return {"ok": False}, 403
    n.is_read = True
    db.session.commit()
    return {"ok": True}
