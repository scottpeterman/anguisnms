# app/utils/database.py
import sqlite3
from contextlib import contextmanager
from flask import current_app

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    db_path = current_app.config.get('DATABASE_PATH', 'assets.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
