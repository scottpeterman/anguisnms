#!/usr/bin/env python3
"""
Capture Files Database Loader
Loads network device capture files into the asset management database
Implements snapshot-based change tracking for configs, version, and inventory
"""

import os
import sqlite3
import re
import hashlib
import difflib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import click

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CaptureLoader:
    """Main loader class for processing network capture files"""

    # Expected capture types based on your directory structure
    CAPTURE_TYPES = [
        'arp', 'authentication', 'authorization', 'bgp-neighbor', 'bgp-summary',
        'bgp-table', 'bgp-table-detail', 'cdp', 'cdp-detail', 'configs',
        'console', 'eigrp-neighbor', 'int-status', 'interface-status',
        'inventory', 'ip_ssh', 'lldp', 'lldp-detail', 'mac', 'ntp_status',
        'ospf-neighbor', 'port-channel', 'routes', 'snmp_server', 'syslog',
        'tacacs', 'version'
    ]

    # Capture types that get full snapshot and change tracking
    CHANGE_TRACKED_TYPES = {'configs', 'version', 'inventory'}

    def __init__(self, db_path: str, diff_output_dir: str = 'diffs'):
        self.db_path = db_path
        self.diff_output_dir = Path(diff_output_dir)
        self.diff_output_dir.mkdir(exist_ok=True)
        self.device_cache = {}  # Cache device IDs by normalized name

    def get_db_connection(self) -> sqlite3.Connection:
        """Get database connection with foreign keys enabled"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def extract_device_info_from_filename(self, file_path: Path) -> Optional[Tuple[str, str, str]]:
        """
        Extract device info from capture filename
        Expected formats:
        - SITE-DEVICE-NAME_capture-type.ext
        - SITE-DEVICE-NAME.capture-type.ext
        - device-name_capture-type.txt

        Returns: (site_code, device_name, capture_type) or None
        """
        filename = file_path.name
        parent_dir = file_path.parent.name

        # Remove common extensions
        name_without_ext = re.sub(r'\.(txt|log|cfg|conf)$', '', filename, flags=re.IGNORECASE)

        # Pattern 1: parent directory is capture type
        if parent_dir in self.CAPTURE_TYPES:
            capture_type = parent_dir
            device_part = name_without_ext
        else:
            # Pattern 2: capture type in filename
            capture_type = None
            for ct in self.CAPTURE_TYPES:
                patterns = [
                    f'_{ct}$',
                    f'_{ct}_',
                    f'\\.{ct}$',
                    f'_{ct.replace("-", "_")}$',
                    f'_{ct.replace("-", "-")}$'
                ]

                for pattern in patterns:
                    if re.search(pattern, name_without_ext, re.IGNORECASE):
                        capture_type = ct
                        device_part = re.sub(pattern, '', name_without_ext, flags=re.IGNORECASE)
                        break

                if capture_type:
                    break

            if not capture_type:
                logger.warning(f"Could not determine capture type for: {filename}")
                return None

        # Extract site and device name from device_part
        site_match = re.match(r'^([A-Za-z]+)-', device_part)
        if site_match:
            site_code = site_match.group(1).upper()
            device_name = device_part.lower()
        else:
            site_code = "UNKNOWN"
            device_name = device_part.lower()

        return site_code, device_name, capture_type

    def get_device_id_by_name(self, conn: sqlite3.Connection, device_name: str, site_code: str = None) -> Optional[int]:
        """Get device ID by normalized name, with optional site filtering"""
        cache_key = f"{site_code}:{device_name}" if site_code else device_name
        if cache_key in self.device_cache:
            return self.device_cache[cache_key]

        cursor = conn.cursor()

        # Exact match only
        if site_code and site_code != "UNKNOWN":
            cursor.execute("""
                SELECT id FROM devices 
                WHERE normalized_name = ? AND site_code = ?
            """, (device_name, site_code))
        else:
            cursor.execute("SELECT id FROM devices WHERE normalized_name = ?", (device_name,))

        row = cursor.fetchone()
        if row:
            device_id = row[0]
            self.device_cache[cache_key] = device_id
            return device_id

        # No match found
        return None
    def get_file_stats(self, file_path: Path) -> Tuple[int, datetime]:
        """Get file size and modification time"""
        stat = file_path.stat()
        return stat.st_size, datetime.fromtimestamp(stat.st_mtime)

    def determine_extraction_success(self, file_path: Path, capture_type: str) -> bool:
        """Determine if capture was successful based on file size"""
        try:
            file_size = file_path.stat().st_size

            if file_size < 50:
                return False

            if capture_type in ['configs', 'config']:
                return file_size > 1000

            return file_size > 100

        except Exception:
            return False

    def determine_command_used(self, capture_type: str) -> str:
        """Map capture type to likely command used"""
        command_mapping = {
            'version': 'show version',
            'inventory': 'show inventory',
            'interface-status': 'show interface status',
            'int-status': 'show interface status',
            'cdp': 'show cdp neighbors',
            'cdp-detail': 'show cdp neighbors detail',
            'lldp': 'show lldp neighbors',
            'lldp-detail': 'show lldp neighbors detail',
            'arp': 'show arp',
            'mac': 'show mac address-table',
            'routes': 'show ip route',
            'bgp-neighbor': 'show bgp neighbors',
            'bgp-summary': 'show bgp summary',
            'bgp-table': 'show bgp',
            'ospf-neighbor': 'show ospf neighbor',
            'eigrp-neighbor': 'show eigrp neighbors',
            'configs': 'show running-config',
            'port-channel': 'show port-channel summary',
            'authentication': 'show authentication',
            'authorization': 'show authorization',
            'ntp_status': 'show ntp status',
            'snmp_server': 'show snmp',
            'syslog': 'show logging',
            'tacacs': 'show tacacs',
            'console': 'show line console',
            'ip_ssh': 'show ip ssh'
        }
        return command_mapping.get(capture_type, f'show {capture_type}')

    def normalize_config_for_diff(self, content: str, capture_type: str) -> str:
        """Remove noise/dynamic content before generating diffs"""
        if capture_type not in self.CHANGE_TRACKED_TYPES:
            return content

        # Generic noise patterns - timestamps and dynamic banners
        noise_patterns = [
            r'^Last login:.*$',
            r'^! Last configuration change at.*$',
            r'^Building configuration.*$',
            r'^Current configuration : \d+ bytes$',
            r'^! NVRAM config last updated.*$',
            r'^\s*!\s*Time:.*$',
            r'^.*ntp clock-period.*$',  # NTP drift compensation
            r'^.*Your previous successful login.*$',
            r'^.*was on \d{4}-\d{2}-\d{2}.*$',
            r'^.*from \d+\.\d+\.\d+\.\d+.*$',
        ]

        lines = []
        for line in content.splitlines():
            # Skip lines matching noise patterns
            if any(re.match(pattern, line.strip()) for pattern in noise_patterns):
                continue
            lines.append(line)

        # Clean excessive whitespace
        result = '\n'.join(lines)
        result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)
        return result.strip()

    def generate_diff(self, old_content: str, new_content: str, capture_type: str = 'configs') -> str:
        """Generate unified diff between two text contents, filtering noise"""
        # Normalize before diffing
        old_normalized = self.normalize_config_for_diff(old_content, capture_type)
        new_normalized = self.normalize_config_for_diff(new_content, capture_type)

        old_lines = old_normalized.splitlines(keepends=True)
        new_lines = new_normalized.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile='previous',
            tofile='current',
            lineterm=''
        )

        return ''.join(diff)

    def save_diff_file(self, device_id: int, capture_type: str, timestamp: datetime, diff_content: str) -> str:
        """Save diff to file and return path"""
        # Create directory structure: diffs/device_id/capture_type/
        device_dir = self.diff_output_dir / str(device_id) / capture_type
        device_dir.mkdir(parents=True, exist_ok=True)

        # Filename with timestamp
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}.diff"
        diff_path = device_dir / filename

        diff_path.write_text(diff_content)
        return str(diff_path)

    def classify_severity(self, capture_type: str, diff_content: str) -> str:
        """Classify change severity based on capture type and diff size"""
        lines_added = diff_content.count('\n+')
        lines_removed = diff_content.count('\n-')
        total_changes = lines_added + lines_removed

        # Critical: large config changes
        if capture_type == 'configs' and total_changes > 50:
            return 'critical'

        # Critical: version changes (firmware upgrades)
        if capture_type == 'version' and total_changes > 0:
            return 'critical'

        # Moderate: any config change
        if capture_type == 'configs' and total_changes > 0:
            return 'moderate'

        # Moderate: inventory changes (hardware swap)
        if capture_type == 'inventory' and total_changes > 5:
            return 'moderate'

        return 'minor'

    def load_with_snapshots(self, file_path: Path, device_id: int, site_code: str,
                            device_name: str, capture_type: str) -> bool:
        """Load with full snapshot and change tracking"""
        try:
            # Read file content
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            file_size, capture_timestamp = self.get_file_stats(file_path)

            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Get previous snapshot
                cursor.execute("""
                    SELECT id, content, content_hash, file_path
                    FROM capture_snapshots 
                    WHERE device_id = ? AND capture_type = ?
                    ORDER BY captured_at DESC LIMIT 1
                """, (device_id, capture_type))

                previous = cursor.fetchone()
                if previous:
                    logger.info(f"  Found previous snapshot: {previous['file_path']}")

                # Skip if unchanged
                if previous and previous['content_hash'] == content_hash:
                    logger.debug(f"No change: {device_name} {capture_type}")
                    return True

                # Insert new snapshot
                cursor.execute("""
                    INSERT INTO capture_snapshots 
                    (device_id, capture_type, captured_at, file_path, file_size, content, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (device_id, capture_type, capture_timestamp.isoformat(),
                      str(file_path), file_size, content, content_hash))

                new_snapshot_id = cursor.lastrowid

                # If previous exists, create change record
                if previous:
                    diff_content = self.generate_diff(previous['content'], content, capture_type)

                    # Only create change record if diff is non-empty
                    if diff_content.strip():
                        diff_path = self.save_diff_file(device_id, capture_type, capture_timestamp, diff_content)

                        lines_added = diff_content.count('\n+')
                        lines_removed = diff_content.count('\n-')
                        severity = self.classify_severity(capture_type, diff_content)

                        cursor.execute("""
                            INSERT INTO capture_changes
                            (device_id, capture_type, detected_at, previous_snapshot_id, 
                             current_snapshot_id, lines_added, lines_removed, diff_path, severity)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (device_id, capture_type, datetime.now().isoformat(), previous['id'],
                              new_snapshot_id, lines_added, lines_removed, diff_path, severity))

                        logger.info(f"CHANGE DETECTED: {device_name} {capture_type} "
                                    f"(+{lines_added}/-{lines_removed} lines, {severity})")
                    else:
                        logger.debug(f"No meaningful changes after normalization: {device_name} {capture_type}")
                else:
                    logger.info(f"Initial snapshot: {device_name} {capture_type}")

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error loading snapshot {file_path}: {e}")
            return False

    def load_current_only(self, file_path: Path, device_id: int, site_code: str,
                          device_name: str, capture_type: str) -> bool:
        """Load only into current captures table (no history)"""
        try:
            file_size, capture_timestamp = self.get_file_stats(file_path)
            extraction_success = self.determine_extraction_success(file_path, capture_type)
            command_used = self.determine_command_used(capture_type)

            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Check if this capture already exists
                cursor.execute("""
                    SELECT id FROM device_captures_current 
                    WHERE device_id = ? AND capture_type = ?
                """, (device_id, capture_type))

                existing = cursor.fetchone()

                if existing:
                    # Update current capture
                    cursor.execute("""
                        UPDATE device_captures_current SET
                            file_path = ?, file_size = ?, capture_timestamp = ?,
                            extraction_success = ?, command_used = ?
                        WHERE id = ?
                    """, (str(file_path), file_size, capture_timestamp.isoformat(),
                          extraction_success, command_used, existing[0]))
                    logger.debug(f"Updated: {device_name} {capture_type}")
                else:
                    # Insert new current capture
                    cursor.execute("""
                        INSERT INTO device_captures_current (
                            device_id, capture_type, file_path, file_size,
                            capture_timestamp, extraction_success, command_used
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (device_id, capture_type, str(file_path), file_size,
                          capture_timestamp.isoformat(), extraction_success, command_used))
                    logger.debug(f"Added: {device_name} {capture_type}")

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return False

    def load_capture_file(self, file_path: Path) -> bool:
        """Load a single capture file into the database"""
        try:
            # Extract device and capture info from filename
            device_info = self.extract_device_info_from_filename(file_path)
            if not device_info:
                logger.warning(f"Could not parse filename: {file_path}")
                return False

            site_code, device_name, capture_type = device_info

            with self.get_db_connection() as conn:
                # Find device ID
                device_id = self.get_device_id_by_name(conn, device_name, site_code)
                logger.info(f"Found device_id: {device_id}")
                if not device_id:
                    logger.warning(f"Device not found for file: {file_path} "
                                   f"(device: {device_name}, site: {site_code})")
                    return False

            # Route to appropriate loader based on capture type
            if capture_type in self.CHANGE_TRACKED_TYPES:
                return self.load_with_snapshots(file_path, device_id, site_code,
                                                device_name, capture_type)
            else:
                return self.load_current_only(file_path, device_id, site_code,
                                              device_name, capture_type)

        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return False

    def load_captures_directory(self, captures_dir: Path, capture_types: List[str] = None) -> Dict[str, int]:
        """Load capture files from directory structure"""
        results = {
            'success': 0,
            'failed': 0,
            'total': 0,
            'by_type': {},
            'changes_detected': 0
        }

        if not captures_dir.exists():
            logger.error(f"Captures directory not found: {captures_dir}")
            return results

        types_to_process = capture_types or self.CAPTURE_TYPES

        # Collect all files to process
        files_to_process = []

        for capture_type in types_to_process:
            type_dir = captures_dir / capture_type
            if type_dir.exists() and type_dir.is_dir():
                patterns = ['*.txt', '*.log', '*.cfg', '*.conf']
                for pattern in patterns:
                    files_to_process.extend(type_dir.glob(pattern))

                results['by_type'][capture_type] = 0
            else:
                logger.warning(f"Capture type directory not found: {type_dir}")

        results['total'] = len(files_to_process)
        logger.info(f"Found {results['total']} capture files to process")

        # Track changes before processing
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM capture_changes")
            changes_before = cursor.fetchone()[0]

        # Process files
        for i, file_path in enumerate(files_to_process, 1):
            if self.load_capture_file(file_path):
                results['success'] += 1
                device_info = self.extract_device_info_from_filename(file_path)
                if device_info:
                    capture_type = device_info[2]
                    if capture_type in results['by_type']:
                        results['by_type'][capture_type] += 1
            else:
                results['failed'] += 1

            if i % 100 == 0 or i == results['total']:
                logger.info(f"Processed {i}/{results['total']} files "
                            f"({results['success']} success, {results['failed']} failed)")

        # Count changes detected
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM capture_changes")
            changes_after = cursor.fetchone()[0]
            results['changes_detected'] = changes_after - changes_before

        return results

    def get_recent_changes_summary(self, hours: int = 24) -> List[Dict]:
        """Get summary of recent changes"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    cc.detected_at,
                    d.name as device_name,
                    s.name as site_name,
                    cc.capture_type,
                    cc.lines_added,
                    cc.lines_removed,
                    cc.severity
                FROM capture_changes cc
                JOIN devices d ON cc.device_id = d.id
                LEFT JOIN sites s ON d.site_code = s.code
                WHERE cc.detected_at > ?
                ORDER BY cc.detected_at DESC
            """, (cutoff,))

            return [dict(row) for row in cursor.fetchall()]


@click.command()
@click.option('--db-path', default='assets.db', help='Path to SQLite database')
@click.option('--captures-dir', default='capture', help='Directory containing capture subdirectories')
@click.option('--diff-dir', default='diffs', help='Directory for storing diff files')
@click.option('--capture-types', help='Comma-separated list of capture types to process')
@click.option('--single-file', help='Process a single capture file')
@click.option('--show-changes', is_flag=True, help='Show recent changes after loading')
@click.option('--changes-hours', default=24, help='Hours of change history to show (default: 24)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
def main(db_path, captures_dir, diff_dir, capture_types, single_file, show_changes, changes_hours, verbose):
    """Load network capture files into the asset management database with change tracking"""

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    loader = CaptureLoader(db_path, diff_dir)

    if single_file:
        file_path = Path(single_file)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return

        logger.info(f"Processing single file: {file_path}")
        success = loader.load_capture_file(file_path)
        if success:
            logger.info("File processed successfully")
        else:
            logger.error("Failed to process file")
    else:
        captures_path = Path(captures_dir)
        logger.info(f"Loading captures from: {captures_path}")
        logger.info(f"Change-tracked types: {', '.join(loader.CHANGE_TRACKED_TYPES)}")

        types_list = None
        if capture_types:
            types_list = [ct.strip() for ct in capture_types.split(',')]
            logger.info(f"Processing capture types: {types_list}")

        results = loader.load_captures_directory(captures_path, types_list)

        logger.info("=" * 70)
        logger.info("CAPTURE LOADING RESULTS")
        logger.info("=" * 70)
        logger.info(f"Total files: {results['total']}")
        logger.info(f"Successfully loaded: {results['success']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Changes detected: {results['changes_detected']}")
        if results['total'] > 0:
            logger.info(f"Success rate: {results['success'] / results['total'] * 100:.1f}%")

        logger.info("\nBy capture type:")
        for capture_type, count in sorted(results['by_type'].items()):
            tracked = " [TRACKED]" if capture_type in loader.CHANGE_TRACKED_TYPES else ""
            logger.info(f"  {capture_type}: {count}{tracked}")

    if show_changes:
        logger.info("\n" + "=" * 70)
        logger.info(f"RECENT CHANGES (Last {changes_hours} hours)")
        logger.info("=" * 70)

        changes = loader.get_recent_changes_summary(changes_hours)
        if changes:
            for change in changes:
                logger.info(f"{change['detected_at']} | {change['device_name']} ({change['site_name']}) | "
                            f"{change['capture_type']} | +{change['lines_added']}/-{change['lines_removed']} | "
                            f"{change['severity'].upper()}")
        else:
            logger.info("No changes detected in this period")


if __name__ == '__main__':
    main()