import json
import base64
import requests
from datetime import datetime
from flask import Blueprint, current_app, redirect, request, url_for, flash
from flask_login import current_user
from ...extensions import db
from ...utils.email import send_email
from ...models import Order, Payment

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


def _mpesa_access_token():
    base_url = current_app.config.get("MPESA_BASE_URL")
    key = current_app.config.get("MPESA_CONSUMER_KEY")
    secret = current_app.config.get("MPESA_CONSUMER_SECRET")
    if not base_url or not key or not secret:
        return None
    try:
        resp = requests.get(
            f"{base_url}/oauth/v1/generate?grant_type=client_credentials",
            auth=(key, secret), timeout=10
        )
        if resp.ok:
            return resp.json().get("access_token")
    except Exception:
        return None
    return None


def _stk_password(short_code: str, passkey: str, timestamp: str) -> str:
    raw = f"{short_code}{passkey}{timestamp}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


@payments_bp.route("/mpesa/start/<int:order_id>")
def start_mpesa(order_id):
    order = Order.query.get_or_404(order_id)
    if float(order.total_amount) <= 0:
        flash("Invalid order amount", "danger")
        return redirect(url_for("orders.my_orders"))

    # Ensure customer phone is available
    phone = (current_user.phone or "").strip() if getattr(current_user, 'is_authenticated', False) else ""
    phone = request.args.get("phone", phone).strip()
    if not phone:
        flash("Add a phone number in your profile to initiate M-Pesa.", "warning")
        return redirect(url_for("account.profile"))

    base_url = current_app.config.get("MPESA_BASE_URL")
    short_code = current_app.config.get("MPESA_SHORT_CODE")
    passkey = current_app.config.get("MPESA_PASSKEY")
    callback_url = current_app.config.get("MPESA_CALLBACK_URL")

    token = _mpesa_access_token()
    if not token or not short_code or not passkey or not callback_url or not base_url:
        # Fallback to stub if not configured
        payment = Payment(order_id=order.id, amount=order.total_amount, status="pending", method="mpesa")
        db.session.add(payment)
        db.session.commit()
        flash("M-Pesa not fully configured. Marked payment pending.", "info")
        return redirect(url_for("orders.my_orders"))

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    password = _stk_password(short_code, passkey, timestamp)
    payload = {
        "BusinessShortCode": short_code,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(float(order.total_amount)),
        "PartyA": phone,
        "PartyB": short_code,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": str(order.id),
        "TransactionDesc": f"Order {order.id} payment",
    }

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.post(f"{base_url}/mpesa/stkpush/v1/processrequest", headers=headers, json=payload, timeout=15)
        data = resp.json() if resp.content else {}
        # Create payment record regardless
        payment = Payment(order_id=order.id, amount=order.total_amount, status="pending", method="mpesa")
        if resp.ok and data.get("ResponseCode") == "0":
            payment.reference = data.get("CheckoutRequestID")
            payment.raw_payload = json.dumps(data)
            flash("M-Pesa STK push sent. Check your phone to authorize.", "info")
        else:
            payment.status = "failed"
            payment.raw_payload = json.dumps(data)
            msg = data.get("errorMessage") or data.get("ResponseDescription") or "Failed to initiate STK"
            flash(msg, "danger")
        db.session.add(payment)
        db.session.commit()
    except Exception:
        payment = Payment(order_id=order.id, amount=order.total_amount, status="failed", method="mpesa")
        db.session.add(payment)
        db.session.commit()
        flash("Network error contacting M-Pesa.", "danger")
    return redirect(url_for("orders.my_orders"))


@payments_bp.route("/mpesa/callback", methods=["POST"])
def mpesa_callback():
    # Daraja sends Body.stkCallback
    data = request.get_json(silent=True) or {}
    body = data.get("Body", {}) if isinstance(data, dict) else {}
    cb = body.get("stkCallback", {})
    checkout_id = cb.get("CheckoutRequestID")
    result_code = cb.get("ResultCode")
    items = cb.get("CallbackMetadata", {}).get("Item", []) if isinstance(cb.get("CallbackMetadata", {}), dict) else []

    # Find payment by checkout id
    payment = None
    if checkout_id:
        payment = Payment.query.filter_by(reference=checkout_id).first()
    # Fallback by AccountReference (order id)
    if not payment:
        try:
            account_ref = next((i.get('Value') for i in items if i.get('Name') == 'AccountReference'), None)
            if account_ref:
                order = Order.query.get(int(account_ref))
                payment = order.payment if order else None
        except Exception:
            payment = None

    if not payment:
        return {"ok": True}

    # Update payment and order
    payment.raw_payload = json.dumps(data)
    if result_code == 0 or result_code == "0":
        payment.status = "paid"
        try:
            if payment.order and payment.order.status in ("pending", "confirmed"):
                payment.order.status = "confirmed"
                # Notify user by email (best-effort)
                if payment.order.user and payment.order.user.email:
                    try:
                        send_email(
                            to=payment.order.user.email,
                            subject=f"Payment received for Order #{payment.order.id}",
                            body=f"Hello,\n\nWe have received your M-Pesa payment for Order #{payment.order.id}. Your order is now confirmed.\n\nThank you for shopping with us."
                        )
                    except Exception:
                        pass
        except Exception:
            pass
    else:
        payment.status = "failed"
    db.session.commit()
    return {"ok": True}
