"""
Centralized extension instances — imported by the app factory and models.
SQLAlchemy/Flask-Migrate removed; MongoDB via PyMongo is the only DB layer.
"""
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager
from flask_pymongo import PyMongo

csrf          = CSRFProtect()
babel         = Babel()
login_manager = LoginManager()
bcrypt        = Bcrypt()
mail          = Mail()
limiter       = Limiter(key_func=get_remote_address)
jwt           = JWTManager()
mongo         = PyMongo()          # mongo.db → database   mongo.cx → MongoClient

try:
    from flask_assets import Environment as AssetsEnvironment
    assets = AssetsEnvironment()
    _assets_available = True
except ImportError:
    assets = None
    _assets_available = False
