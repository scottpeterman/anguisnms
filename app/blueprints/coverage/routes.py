from flask import render_template, request, jsonify, current_app
from pathlib import Path
import yaml
import json
import os
from collections import defaultdict
from datetime import datetime

from . import coverage_bp


# Debug function to understand file structure
def debug_paths():
    """Debug function to understand where we're running from and what's available"""
    print("=== DEBUGGING PATHS ===")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Script directory: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"Directory contents of CWD: {os.listdir('.')}")

    # Check for pcng directory
    if os.path.exists('pcng'):
        print(f"pcng directory exists")
        print(f"pcng contents: {os.listdir('pcng')}")

        # Check for sessions.yaml in pcng
        if os.path.exists('pcng/sessions.yaml'):
            print("✓ Found pcng/sessions.yaml")
        else:
            print("✗ pcng/sessions.yaml NOT found")

        # Check for capture directory
        if os.path.exists('pcng/capture'):
            print("✓ Found pcng/capture directory")
        else:
            print("✗ pcng/capture directory NOT found")

        # Check for fingerprints directory
        if os.path.exists('pcng/fingerprints'):
            print("✓ Found pcng/fingerprints directory")
        else:
            print("✗ pcng/fingerprints directory NOT found")
    else:
        print("✗ pcng directory NOT found in current working directory")

    print("=== END DEBUG ===")


# Call debug function when module loads
debug_paths()


class WebGapReporter:
    """Adapted from your CLI NetworkGapReporter for web use"""

    def __init__(self, yaml_file, capture_dir, fingerprints_dir):
        self.yaml_file = Path(yaml_file)
        self.capture_dir = Path(capture_dir)
        self.fingerprints_dir = Path(fingerprints_dir)
        self.inventory_data = {}
        self.capture_types = []
        self.device_status = defaultdict(dict)

    def load_inventory(self):
        """Load and parse the YAML inventory file."""
        with open(self.yaml_file, 'r') as f:
            self.inventory_data = yaml.safe_load(f)

    def discover_capture_types(self):
        """Discover available capture types from directory structure."""
        if not self.capture_dir.exists():
            return

        self.capture_types = []
        for item in self.capture_dir.iterdir():
            if item.is_dir():
                self.capture_types.append(item.name)
        self.capture_types.sort()

    def analyze_devices(self):
        """Analyze each device's capture status (only devices with fingerprints)."""
        total_devices_in_yaml = 0
        devices_with_fingerprints = 0

        for site in self.inventory_data:
            folder_name = site['folder_name']

            for session in site['sessions']:
                device_name = session['display_name']
                total_devices_in_yaml += 1

                # Check for fingerprint file first - skip if doesn't exist
                fingerprint_file = self.fingerprints_dir / f"{device_name}.json"
                if not fingerprint_file.exists():
                    continue

                devices_with_fingerprints += 1

                # Initialize device status
                device_info = {
                    'folder': folder_name,
                    'host': session.get('host', ''),
                    'vendor': session.get('Vendor', ''),
                    'model': session.get('Model', ''),
                    'fingerprint': True,
                    'captures': {},
                    'total_captures': 0,
                    'missing_captures': 0
                }

                # Load fingerprint data for vendor info
                try:
                    with open(fingerprint_file, 'r') as f:
                        fp_data = json.load(f)
                        if not device_info['vendor']:
                            driver = fp_data.get('additional_info', {}).get('netmiko_driver', '')
                            if 'cisco' in driver:
                                device_info['vendor'] = 'Cisco'
                            elif 'hp' in driver or 'procurve' in driver:
                                device_info['vendor'] = 'HP/Aruba'
                            elif 'arista' in driver:
                                device_info['vendor'] = 'Arista'
                except Exception:
                    pass

                # Check each capture type
                for capture_type in self.capture_types:
                    capture_file = self.capture_dir / capture_type / f"{device_name}.txt"
                    has_capture = capture_file.exists()

                    device_info['captures'][capture_type] = has_capture
                    if has_capture:
                        device_info['total_captures'] += 1
                    else:
                        device_info['missing_captures'] += 1

                self.device_status[device_name] = device_info

    def get_summary_stats(self):
        """Generate summary statistics for the web interface."""
        total_devices = len(self.device_status)
        if total_devices == 0:
            return {}

        # Calculate capture statistics
        capture_stats = {}
        for capture_type in self.capture_types:
            count = sum(1 for d in self.device_status.values() if d['captures'].get(capture_type, False))
            capture_stats[capture_type] = {
                'count': count,
                'total': total_devices,
                'percentage': (count / total_devices) * 100 if total_devices > 0 else 0
            }

        # Perfect capture devices
        perfect_devices = [
            name for name, info in self.device_status.items()
            if info['total_captures'] == len(self.capture_types) and len(self.capture_types) > 0
        ]

        # Zero capture devices
        zero_capture_devices = [
            name for name, info in self.device_status.items()
            if info['total_captures'] == 0
        ]

        return {
            'total_devices': total_devices,
            'capture_types_count': len(self.capture_types),
            'total_successful_captures': sum(d['total_captures'] for d in self.device_status.values()),
            'perfect_capture_count': len(perfect_devices),
            'zero_capture_count': len(zero_capture_devices),
            'capture_stats': capture_stats,
            'perfect_devices': perfect_devices,
            'zero_capture_devices': zero_capture_devices
        }

    def generate_vendor_coverage_matrix(self):
        """Generate vendor coverage analysis by capture type."""
        coverage_data = {
            'vendors': set(),
            'by_capture': defaultdict(lambda: {'vendors': {}, 'vendor_count': 0})
        }

        # Collect all vendors
        for device_info in self.device_status.values():
            vendor = device_info['vendor']
            if vendor and vendor.strip():
                coverage_data['vendors'].add(vendor)

        # Analyze coverage by capture type
        for capture_type in self.capture_types:
            vendor_stats = defaultdict(lambda: {'success': 0, 'total': 0})

            for device_info in self.device_status.values():
                vendor = device_info['vendor'] or 'Unknown'
                vendor_stats[vendor]['total'] += 1

                if device_info['captures'].get(capture_type, False):
                    vendor_stats[vendor]['success'] += 1

            coverage_data['by_capture'][capture_type]['vendors'] = dict(vendor_stats)
            coverage_data['by_capture'][capture_type]['vendor_count'] = len([
                v for v, stats in vendor_stats.items()
                if stats['success'] > 0 and stats['total'] > 0
            ])

        return coverage_data


@coverage_bp.route('/')
def index():
    """Main coverage dashboard."""
    # Configuration - Updated paths to point to pcng directory
    yaml_file = 'pcng/sessions.yaml'
    capture_dir = 'pcng/capture'
    fingerprints_dir = 'pcng/fingerprints'

    try:
        reporter = WebGapReporter(yaml_file, capture_dir, fingerprints_dir)
        reporter.load_inventory()
        reporter.discover_capture_types()
        reporter.analyze_devices()

        summary_stats = reporter.get_summary_stats()
        vendor_coverage = reporter.generate_vendor_coverage_matrix()

        # Group devices by folder for display
        devices_by_folder = defaultdict(list)
        for device_name, device_info in reporter.device_status.items():
            devices_by_folder[device_info['folder']].append((device_name, device_info))

        # Sort devices within each folder
        for folder in devices_by_folder:
            devices_by_folder[folder].sort(key=lambda x: x[0])

        return render_template('coverage/index.html',
                               summary_stats=summary_stats,
                               vendor_coverage=vendor_coverage,
                               devices_by_folder=dict(devices_by_folder),
                               capture_types=reporter.capture_types,
                               generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    except Exception as e:
        current_app.logger.error(f"Coverage analysis failed: {e}")
        return render_template('coverage/index.html',
                               error=f"Failed to generate coverage report: {e}")


@coverage_bp.route('/api/device/<device_name>')
def device_detail(device_name):
    """API endpoint for device-specific coverage details."""
    # Configuration - Updated paths to point to pcng directory
    yaml_file = 'pcng/sessions.yaml'
    capture_dir = 'pcng/capture'
    fingerprints_dir = 'pcng/fingerprints'

    try:
        reporter = WebGapReporter(yaml_file, capture_dir, fingerprints_dir)
        reporter.load_inventory()
        reporter.discover_capture_types()
        reporter.analyze_devices()

        device_info = reporter.device_status.get(device_name)
        if not device_info:
            return jsonify({'error': f'Device {device_name} not found'}), 404

        return jsonify({
            'device_name': device_name,
            'device_info': device_info,
            'capture_types': reporter.capture_types
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@coverage_bp.route('/api/refresh')
def refresh_data():
    """API endpoint to trigger a fresh analysis."""
    try:
        # Configuration - Updated paths to point to pcng directory
        yaml_file = 'pcng/sessions.yaml'
        capture_dir = 'pcng/capture'
        fingerprints_dir = 'pcng/fingerprints'

        reporter = WebGapReporter(yaml_file, capture_dir, fingerprints_dir)
        reporter.load_inventory()
        reporter.discover_capture_types()
        reporter.analyze_devices()

        summary_stats = reporter.get_summary_stats()

        return jsonify({
            'status': 'success',
            'summary': summary_stats,
            'refreshed_at': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500