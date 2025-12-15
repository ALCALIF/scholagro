from sqlalchemy import text
from app import create_app
from app.extensions import db
app = create_app()
with app.app_context():
    db.session.execute(text("ALTER TABLE alembic_version MODIFY version_num VARCHAR(255)"))
    db.session.commit()
    print("ALTER DONE")
