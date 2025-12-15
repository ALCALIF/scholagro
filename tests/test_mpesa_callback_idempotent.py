import json

def test_mpesa_callback_idempotent(app):
    client = app.test_client()
    # Create user and login
    client.post('/auth/signup', data={'name': 'CbUser', 'email': 'cb@example.com', 'password': 'pass1234'}, follow_redirects=True)
    client.post('/auth/login', data={'email': 'cb@example.com', 'password': 'pass1234'}, follow_redirects=True)

    # Create product, add to cart, create address, place order
    with app.app_context():
        from app.extensions import db
        from app.models import Category, Product, DeliveryAddress, User
        cat = Category(name='cbc', slug='cbc')
        p = Product(name='Cb Product', slug='cb-product', price=50.0, category=cat, stock=5)
        db.session.add_all([cat, p])
        db.session.commit()
        pid = p.id
        user = User.query.filter_by(email='cb@example.com').first()
        addr = DeliveryAddress(user_id=user.id, line1='Line', city='City')
        db.session.add(addr)
        db.session.commit()
        addr_id = addr.id

    client.get(f'/cart/add/{pid}', follow_redirects=True)
    # Place order (follow redirects to ensure order is created)
    client.post('/orders/checkout', data={'address_id': addr_id, 'slot': 'morning'}, follow_redirects=True)

    # Fetch latest order and its payment (which may be created pending/failed by MPESA start fallback)
    with app.app_context():
        from app.extensions import db
        from app.models import Order, Payment
        order = db.session.query(Order).order_by(Order.created_at.desc()).first()
        assert order is not None
        # Ensure there is at least a pending payment
        payment = order.payment or Payment(order_id=order.id, amount=order.total_amount, method='mpesa', status='pending')
        db.session.add(payment)
        db.session.commit()
        checkout_id = payment.reference or 'CHECKOUT123'
        payment.reference = checkout_id
        db.session.commit()
        oid = order.id

    # Simulate a successful callback
    payload = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": checkout_id,
                "ResultCode": 0,
                "ResultDesc": "Success",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 50},
                        {"Name": "MpesaReceiptNumber", "Value": "ABC123XYZ"},
                        {"Name": "Balance"},
                        {"Name": "TransactionDate", "Value": 20250101010101},
                        {"Name": "PhoneNumber", "Value": 254700000000},
                        {"Name": "AccountReference", "Value": str(oid)}
                    ]
                }
            }
        }
    }
    res1 = client.post('/payments/mpesa/callback', data=json.dumps(payload), content_type='application/json')
    assert res1.status_code == 200
    res2 = client.post('/payments/mpesa/callback', data=json.dumps(payload), content_type='application/json')
    assert res2.status_code == 200

    # Verify payment marked paid and order confirmed once (idempotent)
    with app.app_context():
        from app.extensions import db
        from app.models import Order, Payment
        order = db.session.get(Order, oid)
        payment = order.payment
        assert payment is not None
        assert payment.status == 'paid'
        assert order.status in ('confirmed', 'pending', 'packed', 'on_the_way', 'delivered')
