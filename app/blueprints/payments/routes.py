import json
import base64
import requests
from datetime import datetime
from flask import Blueprint, current_app, redirect, request, url_for, flash
from flask_login import current_user, login_required
from ...extensions import db, cache, limiter
from ...utils.email import send_email
from ...models import Order, Payment
from ...extensions import socketio
import importlib

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


def _mpesa_access_token():
    base_url = current_app.config.get("MPESA_BASE_URL")
    key = current_app.config.get("MPESA_CONSUMER_KEY")
    secret = current_app.config.get("MPESA_CONSUMER_SECRET")
    if not base_url or not key or not secret:
        return None
    try:
        # Try cache first (cache key: mpesa_access_token)
        try:
            token = cache.get('mpesa_access_token') if cache else None
            if token:
                return token
        except Exception:
            token = None
        resp = requests.get(
            f"{base_url}/oauth/v1/generate?grant_type=client_credentials",
            auth=(key, secret), timeout=10
        )
        if resp is not None and resp.ok:
            token_val = resp.json().get("access_token")
            if token_val:
                try:
                    cache.set('mpesa_access_token', token_val, timeout=55*60)
                except Exception:
                    pass
            return token_val
    except Exception:
        return None
    return None


def _stk_password(short_code: str, passkey: str, timestamp: str) -> str:
    raw = f"{short_code}{passkey}{timestamp}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


@payments_bp.route("/mpesa/start/<int:order_id>")
@limiter.limit("10 per minute")
def start_mpesa(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        from flask import abort
        abort(404)
    if float(order.total_amount) <= 0:
        flash("Invalid order amount", "danger")
        return redirect(url_for("orders.my_orders"))

    # Ensure customer phone is available and valid (format 2547XXXXXXXX)
    phone = (current_user.phone or "").strip() if getattr(current_user, 'is_authenticated', False) else ""
    phone = request.args.get("phone", phone).strip()
    if not phone:
        flash("Add a phone number in your profile or provide it to initiate M-Pesa.", "warning")
        return redirect(url_for("orders.order_detail", order_id=order.id))
    try:
        import re
        if not re.fullmatch(r"2547\d{8}", phone):
            flash("Enter phone in format 2547XXXXXXXX.", "warning")
            return redirect(url_for("orders.order_detail", order_id=order.id))
    except Exception:
        pass

    base_url = current_app.config.get("MPESA_BASE_URL")
    short_code = current_app.config.get("MPESA_SHORT_CODE")
    passkey = current_app.config.get("MPESA_PASSKEY")
    callback_url = current_app.config.get("MPESA_CALLBACK_URL")
    # Optional Lipa na Till support
    till_number = current_app.config.get("MPESA_TILL_NUMBER")
    tx_type = current_app.config.get("MPESA_TRANSACTION_TYPE") or "CustomerPayBillOnline"

    token = _mpesa_access_token()
    if not token or not short_code or not passkey or not callback_url or not base_url:
        # Fallback to stub if not configured
        payment = Payment(order_id=order.id, amount=order.total_amount, status="pending", method="mpesa")
        db.session.add(payment)
        db.session.commit()
        flash("M-Pesa not fully configured. Marked payment pending.", "info")
        return redirect(url_for("orders.my_orders"))

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    # Choose PartyB and transaction type
    use_till = bool(till_number) and tx_type == "CustomerBuyGoodsOnline"
    party_b = (till_number if use_till else short_code)
    password = _stk_password(short_code, passkey, timestamp)
    payload = {
        "BusinessShortCode": short_code,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": tx_type,
        "Amount": int(float(order.total_amount)),
        "PartyA": phone,
        "PartyB": party_b,
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


@payments_bp.route('/stripe/start/<int:order_id>')
@limiter.limit("10 per minute")
def start_stripe(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        from flask import abort
        abort(404)
    if float(order.total_amount) <= 0:
        flash('Invalid order amount', 'danger')
        return redirect(url_for('orders.my_orders'))
    stripe_key = current_app.config.get('STRIPE_SECRET_KEY')
    stripe_pub = current_app.config.get('STRIPE_PUBLISHABLE_KEY')
    if not stripe_key or not stripe_pub:
        flash('Stripe not configured', 'danger')
        return redirect(url_for('orders.my_orders'))
    stripe = importlib.import_module('stripe')
    stripe.api_key = stripe_key
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'kes',
                    'unit_amount': int(float(order.total_amount) * 100),
                    'product_data': {'name': f'Order #{order.id} - ScholaGro'},
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('orders.order_detail', order_id=order.id, _external=True) + '?paid=true',
            cancel_url=url_for('orders.order_detail', order_id=order.id, _external=True),
            metadata={'order_id': str(order.id)}
        )
        # Create payment record if not exists
        p = Payment(order_id=order.id, method='stripe', amount=order.total_amount, status='pending', reference=session.id)
        db.session.add(p)
        db.session.commit()
        return redirect(session.url)
    except Exception as e:
        flash('Failed to create Stripe checkout', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order.id))


@payments_bp.route('/stripe/create_customer', methods=['POST'])
@login_required
@limiter.limit('5 per minute')
def stripe_create_customer():
    stripe_key = current_app.config.get('STRIPE_SECRET_KEY')
    if not stripe_key:
        return {'ok': False, 'message': 'Stripe not configured'}, 400
    stripe = importlib.import_module('stripe')
    stripe.api_key = stripe_key
    user = current_user
    # Create customer if not exists
    if not getattr(user, 'stripe_customer_id', None):
        try:
            cust = stripe.Customer.create(email=user.email, name=user.name)
            user.stripe_customer_id = cust.id
            db.session.commit()
            return {'ok': True, 'customer_id': cust.id}
        except Exception as e:
            return {'ok': False, 'message': str(e)}, 400
    return {'ok': True, 'customer_id': user.stripe_customer_id}


@payments_bp.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    stripe_key = current_app.config.get('STRIPE_SECRET_KEY')
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    stripe = importlib.import_module('stripe')
    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except Exception:
        return {'ok': False}, 400
    # Handle checkout.session.completed
    if event['type'] == 'checkout.session.completed':
        sess = event['data']['object']
        order_id = sess.get('metadata', {}).get('order_id')
        if order_id:
            order = db.session.get(Order, int(order_id))
            if order:
                p = order.payment or Payment(order_id=order.id, method='stripe', amount=order.total_amount)
                p.status = 'paid'
                p.reference = sess.get('id')
                order.status = 'confirmed'
                db.session.add(p)
                db.session.commit()
                try:
                    socketio.emit('order.status', {'order_id': order.id, 'status': order.status}, namespace='/', room=f'user_{order.user_id}')
                except Exception:
                    pass
    return {'ok': True}


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
                order = db.session.get(Order, int(account_ref))
                payment = order.payment if order else None
        except Exception:
            payment = None

    if not payment:
        return {"ok": True}

    # Idempotency: if payment is already processed as paid, ignore
    try:
        if payment.status == 'paid':
            return {"ok": True}
    except Exception:
        pass

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
    try:
        if payment.order and payment.order.user_id:
            socketio.emit('order.status', {'order_id': payment.order.id, 'status': payment.order.status}, namespace='/', room=f'user_{payment.order.user_id}')
    except Exception:
        pass
    return {"ok": True}
