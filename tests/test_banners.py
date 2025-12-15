from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import HomePageBanner, User


def create_admin_user(app):
    with app.app_context():
        u = User(email='admin@example.com', password_hash=generate_password_hash('pass'), name='Admin', is_admin=True)
        db.session.add(u)
        db.session.commit()
    return u


def test_home_banners_limit_and_order(client, app):
    # Create 11 active banners with sort_order increasing
    with app.app_context():
        db.session.query(HomePageBanner).delete()
        for i in range(11):
            db.session.add(HomePageBanner(title=f'B{i}', image_url=f'https://example.com/{i}.jpg', is_active=True, sort_order=i))
        db.session.commit()
    rv = client.get('/')
    html = rv.get_data(as_text=True)
    # Only 10 carousel images should be present
    count = html.count('class="d-block w-100 carousel-img"')
    assert count == 10, f"Expected 10 images, got {count}"
    # Ensure ordering is by sort_order (should show 0..9)
    # find first three images in the html and check their URLs
    idxs = [html.find(f'https://example.com/{i}.jpg') for i in range(11)]
    # The first 10 should be in increasing order; the 11th may be absent or present beyond 10
    order_positions = [pos for pos in idxs if pos != -1]
    assert order_positions == sorted(order_positions), "Image URLs must appear in ascending sort order"


def test_admin_reorder_endpoint(client, app):
    # Login as admin
    with app.app_context():
        db.session.query(HomePageBanner).delete()
        for i in range(3):
            db.session.add(HomePageBanner(title=f'X{i}', image_url=f'https://example.com/x{i}.jpg', is_active=True, sort_order=i))
        db.session.commit()
    create_admin_user(app)
    rv = client.post('/auth/login', data={'email': 'admin@example.com', 'password': 'pass'}, follow_redirects=True)
    assert rv.status_code == 200
    # New desired order: 2,0,1
    resp = client.post('/admin/banners/reorder', json={'order': [2, 0, 1]})
    assert resp.status_code == 200
    # Verify DB order
    with app.app_context():
        items = HomePageBanner.query.order_by(HomePageBanner.sort_order.asc()).all()
        urls = [i.image_url for i in items]
        assert urls[0].endswith('/x2.jpg') and urls[1].endswith('/x0.jpg') and urls[2].endswith('/x1.jpg')
