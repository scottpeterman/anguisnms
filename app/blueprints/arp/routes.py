# app/blueprints/arp/routes.py
from flask import render_template, jsonify, request
from . import arp_bp
from arp_cat_util import ArpCatUtil
import os
import traceback

# Path to ARP database
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
ARP_DB = os.path.join(PROJECT_ROOT, 'arp_cat.db')

print(f"ARP_DB path: {ARP_DB}")
print(f"ARP_DB exists: {os.path.exists(ARP_DB)}")


@arp_bp.route('/search')
def search_page():
    """ARP search interface"""
    return render_template('arp/search.html')


@arp_bp.route('/api/stats')
def api_stats():
    """Get database statistics"""
    try:
        print(f"Attempting to open ARP DB: {ARP_DB}")
        with ArpCatUtil(ARP_DB) as util:
            print("ArpCatUtil opened successfully")
            stats = util.get_statistics()
            print(f"Stats retrieved: {stats}")
            return jsonify(stats)
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR in api_stats: {e}")
        print(f"Full traceback:\n{error_trace}")
        return jsonify({'error': str(e), 'traceback': error_trace}), 500


@arp_bp.route('/api/search/ip/<ip>')
def api_search_ip(ip):
    """Search by IP address"""
    history = request.args.get('history', 'false').lower() == 'true'

    try:
        print(f"Searching for IP: {ip}, history={history}")
        with ArpCatUtil(ARP_DB) as util:
            results = util.search_ip(ip, history=history)
            print(f"Found {len(results)} results")
            return jsonify({
                'success': True,
                'query': ip,
                'count': len(results),
                'results': results
            })
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR in api_search_ip: {e}")
        print(f"Full traceback:\n{error_trace}")
        return jsonify({'success': False, 'error': str(e), 'traceback': error_trace}), 500


@arp_bp.route('/api/search/mac/<mac>')
def api_search_mac(mac):
    """Search by MAC address"""
    history = request.args.get('history', 'false').lower() == 'true'

    try:
        print(f"Searching for MAC: {mac}, history={history}")
        with ArpCatUtil(ARP_DB) as util:
            results = util.search_mac(mac, history=history)
            print(f"Found {len(results)} results")
            return jsonify({
                'success': True,
                'query': mac,
                'count': len(results),
                'results': results
            })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR in api_search_mac: {e}")
        print(f"Full traceback:\n{error_trace}")
        return jsonify({'success': False, 'error': str(e), 'traceback': error_trace}), 500


@arp_bp.route('/api/device/<hostname>')
def api_device_summary(hostname):
    """Get ARP summary for specific device"""
    try:
        with ArpCatUtil(ARP_DB) as util:
            summary = util.get_device_summary(hostname)
            return jsonify({
                'success': True,
                'hostname': hostname,
                'data': summary
            })
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR in api_device_summary: {e}")
        print(f"Full traceback:\n{error_trace}")
        return jsonify({'success': False, 'error': str(e), 'traceback': error_trace}), 500