# app/blueprints/auth/routes.py
from flask import render_template, redirect, url_for, request, session, flash, jsonify
from functools import wraps
import logging
from . import auth_bp
from app.blueprints.auth.auth_manager import AuthenticationManager

logger = logging.getLogger(__name__)

# Initialize authentication manager (will be configured in create_app)
auth_manager = None


def init_auth_manager(config):
    """Initialize authentication manager with application config"""
    global auth_manager
    auth_manager = AuthenticationManager(config)
    logger.info("Authentication manager initialized")


def login_required(f):
    """Decorator to require login for protected routes"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with multi-method authentication support"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        auth_method = request.form.get('auth_method', 'local')
        domain = request.form.get('domain')

        if not username or not password:
            flash('Username and password required', 'error')
            return render_template('auth/login.html')

        # Authenticate using auth manager
        try:
            result = auth_manager.authenticate(
                username=username,
                password=password,
                auth_method=auth_method,
                domain=domain
            )

            if result.success:
                # Set session variables
                session['logged_in'] = True
                session['username'] = result.username
                session['auth_method'] = result.auth_method
                session['groups'] = result.groups or []

                logger.info(f"User {result.username} logged in via {result.auth_method}")

                # Redirect to dashboard or requested page
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('dashboard.index'))
            else:
                flash(f'Authentication failed: {result.error}', 'error')
                logger.warning(f"Failed login attempt for {username}: {result.error}")

        except Exception as e:
            logger.error(f"Login error for {username}: {e}")
            flash('An error occurred during login', 'error')

    # Get available authentication methods
    auth_info = auth_manager.get_available_methods() if auth_manager else {}

    return render_template('auth/login.html', auth_info=auth_info)


@auth_bp.route('/logout')
def logout():
    """Logout and clear session"""
    username = session.get('username', 'Unknown')
    session.clear()
    logger.info(f"User {username} logged out")
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/api/auth/methods', methods=['GET'])
def get_auth_methods():
    """API endpoint to get available authentication methods"""
    if not auth_manager:
        return jsonify({'error': 'Authentication manager not initialized'}), 500

    return jsonify(auth_manager.get_available_methods())


@auth_bp.route('/api/auth/validate', methods=['POST'])
def validate_session():
    """API endpoint to validate current session"""
    if 'logged_in' in session:
        return jsonify({
            'valid': True,
            'username': session.get('username'),
            'auth_method': session.get('auth_method'),
            'groups': session.get('groups', [])
        })
    else:
        return jsonify({'valid': False}), 401