from flask import Blueprint

notes_bp = Blueprint('notes', __name__)

from app.blueprints.notes import routes