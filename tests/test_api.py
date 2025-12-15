import os
import tempfile
import pytest
from app import create_app
from app.extensions import db as _db


@pytest.fixture
def app():
    os.environ['FLASK_ENV'] = 'development'
    app = create_app()
    app.config['TESTING'] = True
    # Disable CSRF for testing convenience (forms are posted directly in tests)
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        _db.create_all()
    yield app
    with app.app_context():
        _db.session.remove()
        _db.drop_all()


def test_health_endpoint(app):
    client = app.test_client()
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert 'db' in data


def test_mini_cart_empty(app):
    client = app.test_client()
    # No auth; endpoint requires auth but mini cart route returns an empty structure for unauthorized
    res = client.get('/cart/mini')
    assert res.status_code in (200, 401)
    # If 200, ensure expected keys
    if res.status_code == 200:
        data = res.get_json()
        assert 'ok' in data


def test_signup_and_login(app):
    client = app.test_client()
    # signup
    res = client.post('/auth/signup', data={'name': 'Test User', 'email': 'test@example.com', 'password': 'pass1234'}, follow_redirects=True)
    assert res.status_code == 200
    # login
    res = client.post('/auth/login', data={'email': 'test@example.com', 'password': 'pass1234'}, follow_redirects=True)
    assert res.status_code == 200
    # Verify login worked by accessing a protected endpoint
    res = client.get('/account/profile')
    assert res.status_code == 200


def test_checkout_mpesa_fallback(app):
    client = app.test_client()
    # create user
    res = client.post('/auth/signup', data={'name': 'Test2', 'email': 'test2@example.com', 'password': 'pass1234'}, follow_redirects=True)
    # login
    res = client.post('/auth/login', data={'email': 'test2@example.com', 'password': 'pass1234'}, follow_redirects=True)
    # create product and add to cart
    with app.app_context():
        from app.models import Product, Category, User
        cat = Category(name='TestCat', slug='testcat')
        p = Product(name='Test Product', slug='test-product', price=100.0, category=cat, stock=10)
        _db.session.add_all([cat, p])
        _db.session.commit()
        pid = p.id
    # add to cart
    res = client.get(f'/cart/add/{pid}', follow_redirects=True)
    assert res.status_code in (200, 302)
    # go to checkout
    res = client.get('/orders/checkout', follow_redirects=True)
    assert res.status_code == 200
