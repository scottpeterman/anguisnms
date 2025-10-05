from flask import render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.blueprints.changes import changes_bp

DB_PATH = 'assets.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@changes_bp.route('/')
def index():
    """Recent changes dashboard"""
    hours = request.args.get('hours', 24, type=int)
    severity = request.args.get('severity', '')

    with get_db() as conn:
        cursor = conn.cursor()

        query = """
            SELECT 
                cc.id,
                cc.device_id,  -- ADD THIS LINE
                cc.detected_at,
                d.name as device_name,
                s.name as site_name,
                cc.capture_type,
                cc.lines_added,
                cc.lines_removed,
                cc.severity,
                cc.diff_path
            FROM capture_changes cc
            JOIN devices d ON cc.device_id = d.id
            LEFT JOIN sites s ON d.site_code = s.code
            WHERE cc.detected_at > ?
        """


        params = [(datetime.now() - timedelta(hours=hours)).isoformat()]

        if severity:
            query += " AND cc.severity = ?"
            params.append(severity)

        query += " ORDER BY cc.detected_at DESC LIMIT 100"

        cursor.execute(query, params)
        changes = [dict(row) for row in cursor.fetchall()]

        # Get summary stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_changes,
                COUNT(DISTINCT device_id) as devices_affected,
                SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical_count,
                SUM(CASE WHEN severity = 'moderate' THEN 1 ELSE 0 END) as moderate_count,
                SUM(CASE WHEN severity = 'minor' THEN 1 ELSE 0 END) as minor_count
            FROM capture_changes
            WHERE detected_at > ?
        """, [(datetime.now() - timedelta(hours=hours)).isoformat()])

        stats = dict(cursor.fetchone())

    return render_template('changes/index.html',
                           changes=changes,
                           stats=stats,
                           hours=hours,
                           severity_filter=severity)


@changes_bp.route('/device/<int:device_id>')
def device_history(device_id):
    """Change history for a specific device"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get device info
        cursor.execute("SELECT * FROM devices WHERE id = ?", (device_id,))
        device = dict(cursor.fetchone())

        # Get changes
        cursor.execute("""
            SELECT 
                cc.*,
                s.name as site_name
            FROM capture_changes cc
            LEFT JOIN devices d ON cc.device_id = d.id
            LEFT JOIN sites s ON d.site_code = s.code
            WHERE cc.device_id = ?
            ORDER BY cc.detected_at DESC
        """, (device_id,))

        changes = [dict(row) for row in cursor.fetchall()]

    return render_template('changes/device_history.html',
                           device=device,
                           changes=changes)


@changes_bp.route('/diff/<int:change_id>')
def view_diff(change_id):
    """View diff for a specific change"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                cc.*,
                d.name as device_name,
                s.name as site_name
            FROM capture_changes cc
            JOIN devices d ON cc.device_id = d.id
            LEFT JOIN sites s ON d.site_code = s.code
            WHERE cc.id = ?
        """, (change_id,))

        change = dict(cursor.fetchone())

    # Read diff file
    diff_content = ""
    if change['diff_path']:
        try:
            diff_content = Path(change['diff_path']).read_text()
        except Exception as e:
            diff_content = f"Error reading diff: {e}"

    return render_template('changes/view_diff.html',
                           change=change,
                           diff_content=diff_content)


@changes_bp.route('/api/recent')
def api_recent_changes():
    """API endpoint for recent changes"""
    hours = request.args.get('hours', 24, type=int)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                cc.detected_at,
                d.name as device_name,
                cc.capture_type,
                cc.severity,
                cc.lines_added,
                cc.lines_removed
            FROM capture_changes cc
            JOIN devices d ON cc.device_id = d.id
            WHERE cc.detected_at > ?
            ORDER BY cc.detected_at DESC
        """, [(datetime.now() - timedelta(hours=hours)).isoformat()])

        changes = [dict(row) for row in cursor.fetchall()]

    return jsonify(changes)