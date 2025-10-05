# app/__init__.py
from flask import Flask
from flask_socketio import SocketIO
import os

from app.blueprints.arp import arp_bp
from app.blueprints.auth.routes import init_auth_manager
from app.blueprints.bulk import bulk_bp
from app.blueprints.capture import capture_bp
from app.blueprints.changes import changes_bp
from app.blueprints.maps import maps_bp
from app.blueprints.notes import notes_bp
from app.blueprints.osversions import osversions_bp
from app.blueprints.roles import roles_bp
from app.blueprints.sites import sites_bp
from app.blueprints.vendors import vendors_bp

socketio = SocketIO()


def create_app(config_name='development'):
    """Application factory pattern"""
    app = Flask(__name__)

    # Basic configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DATABASE'] = os.path.join(app.instance_path, 'assets.db')

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize SocketIO
    socketio.init_app(app, cors_allowed_origins="*")

    # Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.assets import assets_bp
    from app.blueprints.coverage import coverage_bp
    from app.blueprints.components import components_bp
    from app.blueprints.terminal import terminal_bp  # MOVED HERE - import inside function

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(changes_bp, url_prefix='/changes')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(assets_bp, url_prefix='/assets')
    app.register_blueprint(coverage_bp, url_prefix='/coverage')
    app.register_blueprint(maps_bp, url_prefix='/maps')
    app.register_blueprint(arp_bp, url_prefix='/arp')
    app.register_blueprint(components_bp, url_prefix='/components')
    app.register_blueprint(terminal_bp, url_prefix='/terminal')
    app.register_blueprint(capture_bp)
    app.register_blueprint(osversions_bp, url_prefix='/osversions')
    app.register_blueprint(bulk_bp, url_prefix='/bulk')
    app.register_blueprint(sites_bp, url_prefix='/sites')
    app.register_blueprint(roles_bp, url_prefix='/roles')
    app.register_blueprint(vendors_bp, url_prefix='/vendors')
    app.register_blueprint(notes_bp, url_prefix='/notes')

    from app.config_loader import load_config
    config = load_config('config.yaml')
    auth_config = config.get('authentication', {})
    init_auth_manager(auth_config)

    # Coverage analysis configuration
    app.config['SESSIONS_YAML'] = 'pcng/sessions.yaml'
    app.config['CAPTURE_DIR'] = 'pcng/capture'
    app.config['FINGERPRINTS_DIR'] = 'pcng/fingerprints'

    # Root route redirect
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))

    return app, socketio