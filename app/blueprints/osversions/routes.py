# app/blueprints/osversions/routes.py


# app/blueprints/osversions/routes.py
from flask import render_template, request, jsonify, make_response
from . import osversions_bp
from app.utils.database import get_db_connection
import csv
from io import StringIO


@osversions_bp.route('/')
def index():
    """OS Version Dashboard - Using existing device data only"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get version distribution by vendor
            # Change this query at the top of the index() function:
            cursor.execute("""
                SELECT 
                    v.name as vendor,
                    d.os_version,
                    COUNT(d.id) as device_count,
                    GROUP_CONCAT(DISTINCT d.site_code) as sites,
                    MIN(d.id) as example_device_id,
                    MIN(d.name) as example_device_name
                FROM devices d
                LEFT JOIN vendors v ON d.vendor_id = v.id
                WHERE d.os_version IS NOT NULL 
                  AND d.os_version != ''
                  AND d.os_version != 'Unknown'
                GROUP BY v.name, d.os_version
                ORDER BY v.name, device_count DESC
            """)
            version_distribution = [dict(row) for row in cursor.fetchall()]
            print(f"DEBUG: Found {len(version_distribution)} version records")
            if version_distribution:
                print(f"DEBUG: First record = {version_distribution[0]}")

            # Get vendor summary with version counts
            cursor.execute("""
                SELECT 
                    v.name as vendor,
                    COUNT(DISTINCT d.id) as total_devices,
                    COUNT(DISTINCT d.os_version) as unique_versions
                FROM devices d
                LEFT JOIN vendors v ON d.vendor_id = v.id
                WHERE d.os_version IS NOT NULL 
                  AND d.os_version != ''
                  AND d.os_version != 'Unknown'
                GROUP BY v.name
                ORDER BY total_devices DESC
            """)
            vendor_summary = [dict(row) for row in cursor.fetchall()]
            print(f"DEBUG: Found {len(vendor_summary)} vendors")
            if vendor_summary:
                print(f"DEBUG: First vendor = {vendor_summary[0]}")

            # Get devices with missing/unknown versions
            cursor.execute("""
                SELECT 
                    d.id,
                    d.name,
                    d.site_code,
                    v.name as vendor,
                    d.model,
                    d.os_version
                FROM devices d
                LEFT JOIN vendors v ON d.vendor_id = v.id
                WHERE d.os_version IS NULL 
                   OR d.os_version = ''
                   OR d.os_version = 'Unknown'
                ORDER BY v.name, d.name
                LIMIT 50
            """)
            missing_versions = [dict(row) for row in cursor.fetchall()]
            print(f"DEBUG: Found {len(missing_versions)} devices with missing versions")

            # Calculate statistics
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT id) as total_devices,
                    COUNT(DISTINCT CASE 
                        WHEN os_version IS NOT NULL 
                         AND os_version != '' 
                         AND os_version != 'Unknown' 
                        THEN id END) as devices_with_version,
                    COUNT(DISTINCT os_version) as unique_versions
                FROM devices
            """)
            stats = dict(cursor.fetchone())
            stats['missing_count'] = stats['total_devices'] - stats['devices_with_version']
            stats['coverage_pct'] = round((stats['devices_with_version'] / stats['total_devices'] * 100), 1) if stats[
                                                                                                                    'total_devices'] > 0 else 0
            print(f"DEBUG: Stats = {stats}")

            return render_template('osversions/index.html',
                                   version_distribution=version_distribution,
                                   vendor_summary=vendor_summary,
                                   missing_versions=missing_versions,
                                   stats=stats)

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('osversions/index.html',
                               error=str(e),
                               version_distribution=[],
                               vendor_summary=[],
                               missing_versions=[],
                               stats={})





@osversions_bp.route('/vendor/<vendor_name>')
def vendor_detail(vendor_name):
    """Detailed view for a specific vendor's OS versions"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get all versions for this vendor with device lists
            cursor.execute("""
                SELECT 
                    d.os_version,
                    COUNT(d.id) as device_count,
                    GROUP_CONCAT(d.name) as device_names,
                    GROUP_CONCAT(DISTINCT d.site_code) as sites,
                    GROUP_CONCAT(DISTINCT d.model) as models
                FROM devices d
                LEFT JOIN vendors v ON d.vendor_id = v.id
                WHERE v.name = ?
                  AND d.os_version IS NOT NULL 
                  AND d.os_version != ''
                  AND d.os_version != 'Unknown'
                GROUP BY d.os_version
                ORDER BY device_count DESC
            """, (vendor_name,))

            versions = []
            for row in cursor.fetchall():
                version_dict = dict(row)
                # Split concatenated fields into lists
                if version_dict['device_names']:
                    version_dict['devices'] = version_dict['device_names'].split(',')
                if version_dict['sites']:
                    version_dict['sites'] = list(set(version_dict['sites'].split(',')))
                if version_dict['models']:
                    version_dict['models'] = list(set(version_dict['models'].split(',')))
                versions.append(version_dict)

            return render_template('osversions/vendor_detail.html',
                                   vendor=vendor_name,
                                   versions=versions)

    except Exception as e:
        return render_template('osversions/vendor_detail.html',
                               error=str(e),
                               vendor=vendor_name,
                               versions=[])


@osversions_bp.route('/export')
def export_csv():
    """Export OS version report to CSV"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    d.name as device_name,
                    d.site_code,
                    v.name as vendor,
                    d.model,
                    d.os_version,
                    d.management_ip
                FROM devices d
                LEFT JOIN vendors v ON d.vendor_id = v.id
                WHERE d.os_version IS NOT NULL 
                  AND d.os_version != ''
                ORDER BY v.name, d.os_version, d.name
            """)

            devices = cursor.fetchall()

            si = StringIO()
            writer = csv.writer(si)

            writer.writerow(['Device', 'Site', 'Vendor', 'Model', 'OS Version', 'Management IP'])

            for device in devices:
                writer.writerow(device)

            output = si.getvalue()
            si.close()

            response = make_response(output)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = 'attachment; filename=os_versions_report.csv'

            return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500