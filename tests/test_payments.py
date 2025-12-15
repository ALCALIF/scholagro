def test_mpesa_fallback_creates_payment(app):
    client = app.test_client()
    # create user and login
    client.post('/auth/signup', data={'name': 'PayUser', 'email': 'pay@example.com', 'password': 'pass1234'}, follow_redirects=True)
    client.post('/auth/login', data={'email': 'pay@example.com', 'password': 'pass1234'}, follow_redirects=True)
    # Confirm login by visiting a protected page
    res = client.get('/account/profile')
    assert res.status_code == 200
    # create product and add to cart
    # capture user id for DB checks
    with app.app_context():
        from app.models import User
        user_obj = User.query.filter_by(email='pay@example.com').first()
        user_id = user_obj.id
    with app.app_context():
        from app.models import Product, Category, User, CartItem, Order
        from app.extensions import db
        cat = Category(name='paycat', slug='paycat')
        p = Product(name='Pay Product', slug='pay-product', price=120.0, category=cat, stock=10)
        db.session.add_all([cat, p])
        db.session.commit()
        pid = p.id
    res = client.get(f'/cart/add/{pid}', follow_redirects=True)
    # Confirm item is in cart and item quantity is as expected
    res = client.get('/cart/mini')
    data = res.get_json()
    assert data and data.get('count', 0) > 0
    with app.app_context():
        from app.models import CartItem, Product
        from app.extensions import db
        item = CartItem.query.filter_by(user_id=user_id, product_id=pid).first()
        assert item is not None
        assert int(item.quantity) == 1
        prod = db.session.get(Product, pid)
        assert prod is not None
        assert (prod.stock is None) or int(prod.stock) >= int(item.quantity)
    # create address for checkout
    with app.app_context():
        from app.models import DeliveryAddress, User
        user = User.query.filter_by(email='pay@example.com').first()
        user_id = user.id
        addr = DeliveryAddress(user_id=user_id, line1='Test', city='Test')
        db.session.add(addr)
        db.session.commit()
        addr_id = addr.id
    # go to checkout and create order
    res_no_follow = client.post('/orders/checkout', data={'address_id': addr_id, 'slot': 'morning'}, follow_redirects=False)
    # Checkout should redirect either to payment start or back to cart if validation fails
    assert res_no_follow.status_code in (301, 302)
    # Follow redirects to inspect flash message when redirecting back to the cart
    res_follow = client.post('/orders/checkout', data={'address_id': addr_id, 'slot': 'morning'}, follow_redirects=True)
    body = res_follow.get_data(as_text=True)
    # If redirect to cart occurred, check why by looking for common error messages
    if '/cart/' in res_no_follow.headers.get('Location', ''):
        assert ('Insufficient stock' in body) or ('A problem occurred while validating stock' in body) or ('Your cart is empty' in body)
    else:
        assert '/payments/mpesa/start' in res_no_follow.headers.get('Location', '')
    # there should be an order
    with app.app_context():
        from app.models import Order, Payment
        o = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).first()
        assert o is not None
        # start mpesa will create a Payment record in fallback mode if not configured
    # Provide a phone number for the user's profile or as query param to bypass phone requirement
    res = client.get(f'/payments/mpesa/start/{o.id}?phone=0712345678', follow_redirects=True)
    assert res.status_code == 200
    with app.app_context():
        from app.extensions import db
        pmt = Payment.query.filter_by(order_id=o.id).first()
        payments_for_order = Payment.query.filter_by(order_id=o.id).all()
        assert pmt is not None
        assert pmt.status in ('pending','failed','paid')
