from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import Product, User


def create_admin_user(app):
    with app.app_context():
        u = User(email='admin3@example.com', password_hash=generate_password_hash('pass'), name='Admin', is_admin=True)
        db.session.add(u)
        db.session.commit()
    return u


def test_top_picks_page_and_bulk_set(client, app):
    # Create some sample products
    with app.app_context():
        # Create sample products with explicit slug (slug is required)
        p1 = Product(name='TP1', slug='tp1', price=1.0, stock=5, is_top_pick=False)
        p2 = Product(name='TP2', slug='tp2', price=2.0, stock=6, is_top_pick=True)
        p3 = Product(name='TP3', slug='tp3', price=3.0, stock=7, is_top_pick=False)
        db.session.add_all([p1, p2, p3])
        db.session.commit()
        ids = [p1.id, p2.id, p3.id]

    create_admin_user(app)
    client.post('/auth/login', data={'email': 'admin3@example.com', 'password': 'pass'}, follow_redirects=True)

    # Access the top picks page
    rv = client.get('/admin/products/top-picks')
    assert rv.status_code == 200
    html = rv.get_data(as_text=True)
    assert 'Manage Top Picks' in html
    assert 'TP1' in html and 'TP2' in html and 'TP3' in html

    # Set TP1 and TP3 as top picks
    resp = client.post('/admin/products/bulk-set-top-pick', json={'ids': [ids[0], ids[2]], 'value': True})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('ok') is True
    assert str(ids[0]) in data['results'] and data['results'][str(ids[0])] is True
    assert str(ids[2]) in data['results'] and data['results'][str(ids[2])] is True

    # Clear the top picks for p2
    resp2 = client.post('/admin/products/bulk-set-top-pick', json={'ids': [ids[1]], 'value': False})
    assert resp2.status_code == 200
    with app.app_context():
        p2 = db.session.get(Product, ids[1])
        assert p2.is_top_pick is False
