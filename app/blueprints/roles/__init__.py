from flask import Blueprint

roles_bp = Blueprint('roles', __name__)

from app.blueprints.roles import routes