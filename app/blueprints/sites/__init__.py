from flask import Blueprint

sites_bp = Blueprint('sites', __name__)

from app.blueprints.sites import routes