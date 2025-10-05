import json

from app import create_app
import os

if __name__ == '__main__':
    config_name = os.environ.get('FLASK_ENV', 'development')
    app, socketio = create_app(config_name)


    @app.template_filter('from_json')
    def from_json_filter(value):
        """Custom Jinja2 filter to parse JSON strings"""
        if value:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    # Apply login_required to dashboard routes
    from app.blueprints.auth.routes import login_required
    from app.blueprints.dashboard import dashboard_bp

    # Protect dashboard routes
    for endpoint, view_func in dashboard_bp.view_functions.items():
        dashboard_bp.view_functions[endpoint] = login_required(view_func)

    socketio.run(app, debug=True, host='0.0.0.0', port=8086, allow_unsafe_werkzeug=True)