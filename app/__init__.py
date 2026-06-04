"""
OmniFarm Hub — Flask Application Factory
Handles extension initialization, Blueprint registration,
centralized logging, and Flask-Babel i18n setup.
MongoDB replica set replaces SQLAlchemy/MariaDB.
"""
import os
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from flask import Flask, session, request, g, render_template
from config import Config
from .extensions import csrf, babel, login_manager, bcrypt, mail, limiter, jwt, mongo, assets, _assets_available


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class)

    # --- Logging first so every subsequent app.logger call is captured ---
    _configure_logging(app)

    # --- Initialize extensions ---
    csrf.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    jwt.init_app(app)

    # --- MongoDB replica set via Flask-PyMongo ---
    # Flask-PyMongo reads MONGO_URI, creates MongoClient internally, and
    # exposes mongo.db (Database) and mongo.cx (MongoClient).
    #
    # The driver handles RS discovery entirely on its own:
    #   - connects to any seed from the URI seed list
    #   - discovers all members and their roles via hello/isMaster
    #   - opens per-node connection pools
    #   - routes writes to the elected PRIMARY automatically
    #   - monitors topology every heartbeatFrequencyMS in background threads
    #   - fails over transparently when a new PRIMARY is elected
    # No application-level primary tracking or polling is needed.
    mongo.init_app(app)
    app.logger.info('[MongoDB] Flask-PyMongo initialised (RS discovery active)')

    # --- Flask-Assets: CSS bundle (fonts + premium → dist/app.css) --------
    if _assets_available and assets is not None:
        try:
            from flask_assets import Bundle
            assets.init_app(app)
            css_bundle = Bundle(
                'css/fonts.css',
                'css/premium.css',
                filters='cssmin',
                output='dist/app.css',
            )
            assets.register('css_all', css_bundle)
            app.logger.info('[Assets] CSS bundle registered (dist/app.css)')
        except Exception as _ae:
            app.logger.warning('[Assets] Bundle registration failed: %s', _ae)

    # --- Sentry error tracking (only when DSN is set and not a placeholder) ---
    sentry_dsn = app.config.get('SENTRY_DSN', '')
    _dsn_looks_real = (
        sentry_dsn
        and not sentry_dsn.startswith('[PLACEHOLDER')
        and 'xxx' not in sentry_dsn
        and 'yyy' not in sentry_dsn
    )
    if _dsn_looks_real:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[FlaskIntegration()],
                traces_sample_rate=0.05,
            )
            app.logger.info('Sentry error tracking initialized.')
        except Exception as _sentry_err:
            app.logger.warning('Sentry init failed (check SENTRY_DSN): %s', _sentry_err)

    # --- Flask-Login configuration ---
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'

    # --- Flask-Babel: locale selector ---
    def _get_locale() -> str:
        if 'language' in session:
            return session['language']
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            return current_user.language
        return request.accept_languages.best_match(
            app.config['LANGUAGES'],
            default=app.config['BABEL_DEFAULT_LOCALE'],
        )

    babel.init_app(app, locale_selector=_get_locale)

    # --- User loader ---
    from .models.user import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.get_by_id(user_id)

    # --- First-run guard: redirect to /setup when DB is empty ---
    @app.before_request
    def first_run_check():
        from flask import redirect, url_for
        from app.db import get_col
        _bypass = {'auth.setup', 'auth.set_language', 'static'}
        if request.endpoint in _bypass or request.endpoint is None:
            return
        if request.endpoint and (
            request.endpoint.startswith('api.')
            or request.path.startswith('/api/')
            or request.path.startswith('/marketplace/webhook/')
        ):
            return
        if get_col('users').count_documents({}) == 0:
            return redirect(url_for('auth.setup'))

    # --- Context processor: inject helpers into every template ---
    @app.context_processor
    def inject_globals():
        from .marketplace.cart import get_cart_count
        from flask_login import current_user
        from flask_babel import get_locale

        theme = session.get('theme')
        if not theme and current_user and current_user.is_authenticated:
            theme = getattr(current_user, 'theme', 'light')
        if theme not in ('light', 'dark'):
            theme = 'light'

        return {
            'now':               datetime.now(timezone.utc),
            'app_name':          'OmniFarm Hub',
            'cart_count':        get_cart_count(),
            'user_theme':        theme,
            'get_locale':        get_locale,
            'use_assets_bundle': _assets_available,
        }

    # --- Register Blueprints ---
    from .main import main_bp
    from .auth import auth_bp
    from .aquaculture import aquaculture_bp
    from .poultry import poultry_bp
    from .cuniculture import cuniculture_bp
    from .marketplace import marketplace_bp
    from .api import api_bp
    from .iot import iot_bp
    from .finance import finance_bp
    from .health import health_bp
    from .reports import reports_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(aquaculture_bp)
    app.register_blueprint(poultry_bp)
    app.register_blueprint(cuniculture_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(iot_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(reports_bp)

    # --- IoT background scheduler ---
    from .iot.scheduler import init_scheduler
    init_scheduler(app)

    # --- HTTP error handlers ---
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html', title='Accès refusé'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html', title='Page introuvable'), 404

    @app.errorhandler(413)
    def too_large(e):
        from flask import request as req, jsonify
        if req.path.startswith('/api/'):
            return jsonify(error='Payload too large.'), 413
        return render_template('errors/413.html', title='Fichier trop grand'), 413

    @app.errorhandler(429)
    def rate_limited(e):
        from flask import request as req, jsonify
        if req.path.startswith('/api/'):
            return jsonify(error='Too many requests. Please slow down.'), 429
        return render_template('errors/429.html', title='Trop de requêtes'), 429

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error('Internal Server Error: %s', e, exc_info=True)
        return render_template('errors/500.html', title='Erreur serveur'), 500

    app.logger.info('OmniFarm Hub ready — blueprints: %s', list(app.blueprints.keys()))
    return app


def _configure_logging(app: Flask) -> None:
    log_level_str = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    log_file = app.config.get('LOG_FILE', 'logs/omnifarm.log')

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    formatter = logging.Formatter(
        fmt='[%(asctime)s] %(levelname)-8s %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024,
                                       backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    import sys
    console_handler = logging.StreamHandler(
        stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1,
                    closefd=False)
    )
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    for handler in [file_handler, console_handler]:
        app.logger.addHandler(handler)
        logging.getLogger('apscheduler').addHandler(handler)
        logging.getLogger('pymodbus').addHandler(handler)

    app.logger.setLevel(log_level)
    app.logger.propagate = False
