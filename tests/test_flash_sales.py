from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import FlashSale, Product, Category, User
from datetime import datetime, timedelta


def create_admin_user(app):
    """Create an admin user for testing."""
    with app.app_context():
        u = User(
            email='admin@example.com',
            password_hash=generate_password_hash('pass'),
            name='Admin',
            is_admin=True
        )
        db.session.add(u)
        db.session.commit()
    return u


def create_product(app):
    """Create a test product for flash sale tests."""
    with app.app_context():
        cat = Category(name='Test Category', slug='test-cat')
        db.session.add(cat)
        db.session.flush()
        p = Product(
            name='Test Product',
            slug='test-product',
            price=100.0,
            category_id=cat.id,
            is_active=True
        )
        db.session.add(p)
        db.session.commit()
        return p.id, cat.id


def test_flash_sale_requires_admin(client, app):
    """Test that flash sale routes require admin access."""
    response = client.get('/admin/flash-sales', follow_redirects=True)
    # Should redirect to login since not authenticated
    assert response.status_code == 200
    assert b'login' in response.data.lower() or b'email' in response.data.lower()


def test_flash_sale_create(client, app):
    """Test creating a flash sale."""
    create_admin_user(app)
    product_id, _ = create_product(app)
    
    # Login as admin
    rv = client.post('/auth/login', data={'email': 'admin@example.com', 'password': 'pass'}, follow_redirects=True)
    assert rv.status_code == 200
    
    start = datetime.utcnow() + timedelta(hours=1)
    end = datetime.utcnow() + timedelta(hours=3)
    
    response = client.post('/admin/flash-sales', data={
        'product_id': product_id,
        'discount_percent': 20,
        'starts_at': start.isoformat(),
        'ends_at': end.isoformat(),
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Verify DB record created
    with app.app_context():
        fs = FlashSale.query.filter_by(product_id=product_id).first()
        assert fs is not None
        assert fs.discount_percent == 20
        # allow small time difference due to serialization precision
        assert abs((fs.starts_at - start).total_seconds()) < 2


def test_flash_sale_overlap_prevention(client, app):
    """Test that overlapping flash sales are prevented."""
    create_admin_user(app)
    product_id, _ = create_product(app)
    
    # Login as admin
    rv = client.post('/auth/login', data={'email': 'admin@example.com', 'password': 'pass'}, follow_redirects=True)
    assert rv.status_code == 200
    
    start1 = datetime.utcnow() + timedelta(hours=1)
    end1 = datetime.utcnow() + timedelta(hours=5)
    start2 = datetime.utcnow() + timedelta(hours=3)
    end2 = datetime.utcnow() + timedelta(hours=7)
    
    # Create first flash sale
    with app.app_context():
        fs1 = FlashSale(
            product_id=product_id,
            discount_percent=20,
            original_price=100.0,
            starts_at=start1,
            ends_at=end1,
            is_active=True
        )
        db.session.add(fs1)
        db.session.commit()
    
    # Try to create overlapping flash sale
    response = client.post('/admin/flash-sales', data={
        'product_id': product_id,
        'discount_percent': 15,
        'starts_at': start2.isoformat(),
        'ends_at': end2.isoformat(),
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Ensure no second overlapping sale was created
    with app.app_context():
        cnt = FlashSale.query.filter_by(product_id=product_id).count()
        assert cnt == 1


def test_flash_sale_edit(client, app):
    """Test editing a flash sale."""
    create_admin_user(app)
    product_id, _ = create_product(app)
    
    # Login as admin
    rv = client.post('/auth/login', data={'email': 'admin@example.com', 'password': 'pass'}, follow_redirects=True)
    assert rv.status_code == 200
    
    start = datetime.utcnow() + timedelta(hours=1)
    end = datetime.utcnow() + timedelta(hours=5)
    
    # Create flash sale
    with app.app_context():
        fs = FlashSale(
            product_id=product_id,
            discount_percent=20,
            original_price=100.0,
            starts_at=start,
            ends_at=end,
            is_active=True
        )
        db.session.add(fs)
        db.session.commit()
        fs_id = fs.id
    
    new_start = datetime.utcnow() + timedelta(hours=2)
    new_end = datetime.utcnow() + timedelta(hours=6)
    
    response = client.post(f'/admin/flash-sales/{fs_id}/edit', data={
        'product_id': product_id,
        'discount_percent': 25,
        'starts_at': new_start.isoformat(),
        'ends_at': new_end.isoformat(),
    }, follow_redirects=True)
    
    assert response.status_code == 200
    with app.app_context():
        fs = FlashSale.query.get(fs_id)
        assert fs is not None
        assert fs.discount_percent == 25
        # allow small time difference due to serialization precision
        assert abs((fs.starts_at - new_start).total_seconds()) < 2


def test_flash_sale_delete_restores_price(client, app):
    """Test that deleting a flash sale restores the original product price."""
    create_admin_user(app)
    product_id, _ = create_product(app)
    
    # Login as admin
    rv = client.post('/auth/login', data={'email': 'admin@example.com', 'password': 'pass'}, follow_redirects=True)
    assert rv.status_code == 200
    
    original_price = 100.0
    start = datetime.utcnow() + timedelta(hours=1)
    end = datetime.utcnow() + timedelta(hours=5)
    
    # Create flash sale
    with app.app_context():
        fs = FlashSale(
            product_id=product_id,
            discount_percent=20,
            original_price=original_price,
            starts_at=start,
            ends_at=end,
            is_active=True
        )
        db.session.add(fs)
        db.session.commit()
        fs_id = fs.id
        
        # Simulate price update in product
        product = Product.query.get(product_id)
        product.price = 80.0
        db.session.add(product)
        db.session.commit()
    
    # Delete flash sale
    response = client.post(f'/admin/flash-sales/{fs_id}/delete', follow_redirects=True)
    
    assert response.status_code == 200
    # Check flash sale removed and price restored
    with app.app_context():
        fs = FlashSale.query.get(fs_id)
        assert fs is None
        product = Product.query.get(product_id)
        assert float(product.price) == original_price


def test_flash_sale_invalid_dates(client, app):
    """Test that flash sales reject invalid date ranges."""
    create_admin_user(app)
    product_id, _ = create_product(app)
    
    # Login as admin
    rv = client.post('/auth/login', data={'email': 'admin@example.com', 'password': 'pass'}, follow_redirects=True)
    assert rv.status_code == 200
    
    start = datetime.utcnow() + timedelta(hours=5)
    end = datetime.utcnow() + timedelta(hours=1)  # End before start
    
    response = client.post('/admin/flash-sales', data={
        'product_id': product_id,
        'discount_percent': 20,
        'starts_at': start.isoformat(),
        'ends_at': end.isoformat(),
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Ensure no flash sale created due to invalid dates
    with app.app_context():
        cnt = FlashSale.query.filter_by(product_id=product_id).count()
        assert cnt == 0
