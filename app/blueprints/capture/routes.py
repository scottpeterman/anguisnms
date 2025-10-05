# app/blueprints/capture/routes.py
from flask import render_template, request, jsonify, current_app
from . import capture_bp
from app.utils.database import get_db_connection
import re
import os


@capture_bp.route('/')
@capture_bp.route('/search')
def search():
    """Capture search interface"""
    with get_db_connection() as conn:
        # Get available capture types from the coverage view
        cursor = conn.execute("""
            SELECT capture_type, device_count, success_rate, latest_capture
            FROM v_capture_coverage 
            ORDER BY device_count DESC
        """)
        capture_types = [dict(row) for row in cursor.fetchall()]

        # Get basic stats
        cursor = conn.execute("SELECT COUNT(*) as total_devices FROM devices")
        total_devices = cursor.fetchone()['total_devices']

        cursor = conn.execute("SELECT COUNT(DISTINCT capture_type) as total_types FROM device_captures_current")
        total_types = cursor.fetchone()['total_types']

    return render_template('capture/search.html',
                           capture_types=capture_types,
                           total_devices=total_devices,
                           total_types=total_types)


@capture_bp.route('/api/search', methods=['POST'])
def api_search():
    """API endpoint for capture content search"""
    data = request.get_json()
    query = data.get('query', '').strip()
    capture_types = data.get('capture_types', [])
    devices = data.get('devices', [])
    case_sensitive = data.get('case_sensitive', False)
    regex_mode = data.get('regex_mode', False)

    if not query:
        return jsonify({'error': 'Search query is required'}), 400

    results = []

    with get_db_connection() as conn:
        # Build the base query
        where_conditions = []
        params = []

        if capture_types:
            placeholders = ','.join('?' * len(capture_types))
            where_conditions.append(f"dcc.capture_type IN ({placeholders})")
            params.extend(capture_types)

        if devices:
            placeholders = ','.join('?' * len(devices))
            where_conditions.append(f"d.id IN ({placeholders})")
            params.extend(devices)

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Get captures to search through
        cursor = conn.execute(f"""
            SELECT dcc.id, dcc.device_id, dcc.capture_type, dcc.file_path,
                   d.name as device_name, d.management_ip, s.name as site_name
            FROM device_captures_current dcc
            JOIN devices d ON dcc.device_id = d.id
            LEFT JOIN sites s ON d.site_code = s.code
            {where_clause}
            ORDER BY d.name, dcc.capture_type
        """, params)

        captures = cursor.fetchall()

    # Search through capture files
    for capture in captures:
        try:
            if os.path.exists(capture['file_path']):
                with open(capture['file_path'], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                if search_content(content, query, case_sensitive, regex_mode):
                    # Find matching lines
                    lines = content.split('\n')
                    matching_lines = []

                    for i, line in enumerate(lines, 1):
                        if search_content(line, query, case_sensitive, regex_mode):
                            # Get context around the match
                            start = max(0, i - 2)
                            end = min(len(lines), i + 3)
                            context = lines[start:end]

                            matching_lines.append({
                                'line_number': i,
                                'line': line.strip(),
                                'context': context
                            })

                            # Limit matches per file
                            if len(matching_lines) >= 10:
                                break

                    results.append({
                        'device_id': capture['device_id'],
                        'device_name': capture['device_name'],
                        'management_ip': capture['management_ip'],
                        'site_name': capture['site_name'],
                        'capture_type': capture['capture_type'],
                        'file_path': capture['file_path'],
                        'matches': matching_lines
                    })
        except Exception as e:
            current_app.logger.error(f"Error searching file {capture['file_path']}: {str(e)}")
            continue

    return jsonify({
        'results': results,
        'total_matches': len(results),
        'query': query
    })


def search_content(content, query, case_sensitive=False, regex_mode=False):
    """Search content with different modes"""
    try:
        if regex_mode:
            flags = 0 if case_sensitive else re.IGNORECASE
            return bool(re.search(query, content, flags))
        else:
            search_content = content if case_sensitive else content.lower()
            search_query = query if case_sensitive else query.lower()
            return search_query in search_content
    except re.error:
        # If regex is invalid, fall back to literal search
        search_content = content if case_sensitive else content.lower()
        search_query = query if case_sensitive else query.lower()
        return search_query in search_content


@capture_bp.route('/api/types')
def api_capture_types():
    """Get available capture types"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT capture_type, device_count, success_rate, latest_capture
            FROM v_capture_coverage 
            ORDER BY capture_type
        """)
        types = [dict(row) for row in cursor.fetchall()]

    return jsonify(types)


@capture_bp.route('/api/view', methods=['POST'])
def api_view_capture():
    """API endpoint to view full capture content"""
    data = request.get_json()
    device_id = data.get('device_id')
    capture_type = data.get('capture_type')

    if not device_id or not capture_type:
        return jsonify({'error': 'Device ID and capture type are required'}), 400

    with get_db_connection() as conn:
        # Get capture file info
        cursor = conn.execute("""
            SELECT dcc.file_path, dcc.file_size, dcc.capture_timestamp,
                   d.name as device_name, d.management_ip, s.name as site_name
            FROM device_captures_current dcc
            JOIN devices d ON dcc.device_id = d.id
            LEFT JOIN sites s ON d.site_code = s.code
            WHERE dcc.device_id = ? AND dcc.capture_type = ?
        """, (device_id, capture_type))

        capture = cursor.fetchone()

        if not capture:
            return jsonify({'error': 'Capture not found'}), 404

        file_path = capture['file_path']

        if not os.path.exists(file_path):
            return jsonify({'error': 'Capture file not found on disk'}), 404

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            return jsonify({
                'content': content,
                'file_path': file_path,
                'file_size': capture['file_size'],
                'capture_timestamp': capture['capture_timestamp'],
                'device_name': capture['device_name'],
                'management_ip': capture['management_ip'],
                'site_name': capture['site_name']
            })

        except Exception as e:
            current_app.logger.error(f"Error reading capture file {file_path}: {str(e)}")
            return jsonify({'error': f'Error reading capture file: {str(e)}'}), 500


@capture_bp.route('/api/devices')
def api_devices():
    """Get devices for filtering"""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT DISTINCT d.id, d.name, d.management_ip, s.name as site_name
            FROM devices d
            LEFT JOIN sites s ON d.site_code = s.code
            WHERE d.id IN (SELECT DISTINCT device_id FROM device_captures_current)
            ORDER BY d.name
        """)
        devices = [dict(row) for row in cursor.fetchall()]

    return jsonify(devices)