import pytest

def test_add_and_update_cart(app):
    client = app.test_client()
    # create user and login
    client.post('/auth/signup', data={'name': 'CTester', 'email': 'cart@example.com', 'password': 'pass1234'}, follow_redirects=True)
    client.post('/auth/login', data={'email': 'cart@example.com', 'password': 'pass1234'}, follow_redirects=True)
    # create product
    with app.app_context():
        from app.models import Product, Category
        cat = Category(name='c2', slug='c2')
        p = Product(name='Cart Product', slug='cart-product', price=50.0, category=cat, stock=100)
        from app.extensions import db
        db.session.add_all([cat, p])
        db.session.commit()
        pid = p.id
    # add to cart via JSON
    res = client.post('/cart/add', json={'product_id': pid})
    assert res.status_code in (200, 201)
    data = res.get_json()
    assert data.get('ok')
    # update quantity
    cid = None
    with app.app_context():
        from app.models import CartItem
        item = CartItem.query.filter_by(product_id=pid).first()
        cid = item.id
    res = client.post('/cart/update', json={'item_id': cid, 'quantity': 3})
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('quantity') == 3
