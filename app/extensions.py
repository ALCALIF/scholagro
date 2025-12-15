from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_caching import Cache
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
csrf = CSRFProtect()
cache = Cache()
# async_mode will be provided in app.__init__ via init_app
socketio = SocketIO()
limiter = Limiter(key_func=get_remote_address)

# Export objects for importers
__all__ = ['db', 'migrate', 'login_manager', 'csrf', 'cache', 'socketio', 'limiter']
