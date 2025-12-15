import sys
from app import create_app
from app.extensions import db
from werkzeug.security import generate_password_hash
from app.models import User, Order
def test_stripe_not_imported_on_app_start(app):
    # Ensure stripe is not in sys.modules after create_app
    assert 'stripe' not in sys.modules
    # Create the app (the 'app' fixture creates app already); confirm not imported
    assert 'stripe' not in sys.modules
    # Ensure that accessing payments routes that use stripe import it lazily
    with app.test_client() as client:
        # Call a non-stripe route to ensure app runs
        r = client.get('/')
        assert r.status_code in (200, 302)
        # Stripe still shouldn't be imported by non-stripe route
        assert 'stripe' not in sys.modules
        # Create a user and order so the payment route is reachable, and set stripe config to force import
        with app.app_context():
            u = User(email='lazy@local', password_hash=generate_password_hash('pass'), name='Lazy', is_admin=False)
            db.session.add(u)
            db.session.commit()
            o = Order(user_id=u.id, total_amount=10.0)
            db.session.add(o)
            db.session.commit()
            orderid = o.id
        app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
        app.config['STRIPE_PUBLISHABLE_KEY'] = 'pk_test_123'
        # Now call stripe route which should import stripe lazily
        client.get(f'/payments/stripe/start/{orderid}')
        # After calling, stripe may be imported
        assert 'stripe' in sys.modules
