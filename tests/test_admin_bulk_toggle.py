from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import Product, User


def create_admin_user(app):
    with app.app_context():
        u = User(email='admin2@example.com', password_hash=generate_password_hash('pass'), name='Admin', is_admin=True)
        db.session.add(u)
        db.session.commit()
    return u


def test_bulk_toggle_top_pick(client, app):
    # setup: create two products, one top pick and one not
    from app.models import Product
    with app.app_context():
        # Create test products with slugs (slug is not nullable in the model)
        p1 = Product(name='Prod A', slug='prod-a', price=1.0, stock=5, is_top_pick=False)
        p2 = Product(name='Prod B', slug='prod-b', price=2.0, stock=10, is_top_pick=True)
        db.session.add_all([p1, p2])
        db.session.commit()
        id1, id2 = p1.id, p2.id
    # login as admin
    create_admin_user(app)
    client.post('/auth/login', data={'email': 'admin2@example.com', 'password': 'pass'}, follow_redirects=True)

    resp = client.post('/admin/products/bulk-toggle-top-pick', json={'ids': [id1, id2]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get('ok') is True
    assert str(id1) in data.get('results')
    assert str(id2) in data.get('results')
    # check DB values toggled
    with app.app_context():
        p1 = db.session.get(Product, id1)
        p2 = db.session.get(Product, id2)
        assert p1.is_top_pick is True
        assert p2.is_top_pick is False
