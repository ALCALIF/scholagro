from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash

a = create_app()
with a.app_context():
    email = "adminscholagro@gmail.com"
    name = "Admin"
    pwd = "@scholalcalif2030"
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=name, password_hash=generate_password_hash(pwd, method='pbkdf2:sha256'), is_admin=True)
        db.session.add(user)
    else:
        user.is_admin = True
        user.password_hash = generate_password_hash(pwd, method='pbkdf2:sha256')
    db.session.commit()
    print("ADMIN_OK", user.id)
