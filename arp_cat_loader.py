#!/usr/bin/env python3
"""
ARP Cat Loader

Loads ARP capture files from assets.db using the v_capture_details view
and processes them through TextFSM parsing into the arp_cat.db database.
"""

import os
import sys
import sqlite3
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import ipaddress

# Import our ARP Cat utility
from arp_cat_util import ArpCatUtil, get_parser

# Import TextFSM engine if available
try:
    from tfsm_fire import TextFSMAutoEngine

    TEXTFSM_AVAILABLE = True
except ImportError:
    try:
        sys.path.append('./Anguis')
        from tfsm_fire import TextFSMAutoEngine

        TEXTFSM_AVAILABLE = True
    except ImportError:
        TEXTFSM_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ArpCaptureLoader:
    """Loads ARP captures from assets.db and processes them into arp_cat.db"""

    def __init__(self, assets_db_path: str = "assets.db",
                 arp_cat_db_path: str = "arp_cat.db",
                 textfsm_db_path: str = "Anguis/tfsm_templates.db"):
        """
        Initialize the ARP capture loader.

        Args:
            assets_db_path: Path to assets database
            arp_cat_db_path: Path to ARP cat database
            textfsm_db_path: Path to TextFSM templates database
        """
        self.assets_db_path = assets_db_path
        self.arp_cat_db_path = arp_cat_db_path
        self.textfsm_db_path = textfsm_db_path
        self.textfsm_engine = None

        # Initialize TextFSM engine
        self._initialize_textfsm()

    def _initialize_textfsm(self):
        """Initialize TextFSM engine with fallback paths"""
        if not TEXTFSM_AVAILABLE:
            logger.warning("TextFSM not available - processing will fail")
            return

        # Try multiple paths for the TextFSM database
        potential_paths = [
            self.textfsm_db_path,
            "tfsm_templates.db",
            "Anguis/tfsm_templates.db",
            "./tfsm_templates.db"
        ]

        for db_path in potential_paths:
            if os.path.exists(db_path):
                try:
                    self.textfsm_engine = TextFSMAutoEngine(db_path, verbose=False)
                    logger.info(f"TextFSM engine initialized with: {db_path}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to initialize TextFSM with {db_path}: {e}")

        logger.error("No TextFSM templates found - processing will fail")

    def _create_vendor_filter(self, vendor_name: str, device_type: str = None) -> List[str]:
        """
        Create TextFSM filter based on vendor and device type.
        Uses exact template names from the TextFSM database.
        """
        if not vendor_name:
            return ['show_ip_arp', 'arp']

        vendor_lower = vendor_name.lower()
        filters = []

        logger.debug(f"Creating filters for vendor: {vendor_name} (normalized: {vendor_lower})")

        # Vendor-specific ARP command filters - using exact template names from database
        vendor_filters = {
            'cisco': [
                'cisco_ios_show_ip_arp',  # Exact match from your database
                'cisco_nxos_show_ip_arp',  # Exact match from your database
                'cisco_ios_show_arp',  # Exact match from your database
                'show_ip_arp',  # Generic fallback
                'ip_arp'  # Shorter fallback
            ],
            'arista': [
                'arista_eos_show_arp',
                'arista_show_arp',
                'eos_show_arp'
            ],
            'juniper': [
                'juniper_junos_show_arp',
                'juniper_show_arp',
                'junos_show_arp'
            ],
            'hp': [
                'hp_procurve_show_arp',
                'hp_comware_show_arp',
                'hp_show_arp'
            ],
            'aruba': [
                'aruba_os_show_arp',
                'aruba_show_arp'
            ],
            'fortinet': [
                'fortinet_show_arp',
                'fortigate_show_arp'
            ],
            'paloalto': [
                'paloalto_panos_show_arp',
                'panos_show_arp'
            ]
        }

        # Find matching vendor filters
        for vendor_key, vendor_filter_list in vendor_filters.items():
            if vendor_key in vendor_lower:
                filters.extend(vendor_filter_list)
                logger.debug(f"Added {len(vendor_filter_list)} vendor-specific filters for {vendor_key}")
                break

        # Add generic filters as fallback
        generic_filters = ['show_arp', 'arp']
        filters.extend(generic_filters)
        logger.debug(f"Added {len(generic_filters)} generic filters")

        logger.debug(f"Total filters to try: {filters}")
        return filters

    def _parse_arp_with_textfsm(self, content: str, vendor: str, device_type: str = None) -> Optional[Dict]:
        """Parse ARP content using TextFSM with vendor-specific filters"""
        if not self.textfsm_engine:
            logger.error("TextFSM engine not available")
            return None

        try:
            filter_attempts = self._create_vendor_filter(vendor, device_type)
            logger.info(f"Trying TextFSM filters for vendor '{vendor}': {filter_attempts}")

            best_result = None
            best_score = 0

            for i, filter_string in enumerate(filter_attempts, 1):
                logger.debug(f"Attempt {i}/{len(filter_attempts)}: Testing filter '{filter_string}'")

                try:
                    # Handle different return formats from tfsm_fire
                    result = self.textfsm_engine.find_best_template(content, filter_string)

                    if len(result) == 4:
                        template, parsed_data, score, template_content = result
                    elif len(result) == 3:
                        template, parsed_data, score = result
                        template_content = None
                    else:
                        logger.debug(f"  Unexpected result format: {len(result)} items")
                        continue

                    logger.debug(f"  Template found: '{template}' with score {score}")
                    logger.debug(f"  Parsed {len(parsed_data) if parsed_data else 0} records")

                    # Debug the parsed data structure
                    if parsed_data and len(parsed_data) > 0:
                        sample_record = parsed_data[0]
                        if isinstance(sample_record, dict):
                            logger.debug(f"  Sample record fields: {list(sample_record.keys())}")
                            logger.debug(f"  Sample record: {sample_record}")
                        elif isinstance(sample_record, list):
                            logger.debug(f"  Sample record (list): {sample_record}")
                        else:
                            logger.debug(f"  Sample record type: {type(sample_record)}")

                    if score > best_score and parsed_data:
                        best_score = score
                        best_result = {
                            'template_name': template,
                            'score': score,
                            'parsed_data': parsed_data,
                            'filter_used': filter_string,
                            'template_content': template_content
                        }

                        logger.info(f"  ✓ NEW BEST MATCH: {template} (score: {score}, records: {len(parsed_data)})")

                        # Show template schema info
                        if template_content:
                            logger.debug("  Template content preview:")
                            lines = template_content.split('\n')[:10]  # First 10 lines
                            for line in lines:
                                if line.strip():
                                    logger.debug(f"    {line}")

                        # High confidence match - stop searching
                        if score > 70:
                            logger.info(f"  High confidence match (>{70}) - stopping search")
                            break
                    else:
                        logger.debug(f"  Score {score} not better than current best {best_score}")

                except Exception as e:
                    logger.debug(f"  Filter '{filter_string}' failed: {e}")
                    continue

            if best_result and best_result['score'] > 2:
                logger.info(f"FINAL RESULT: Template '{best_result['template_name']}' " +
                            f"(score: {best_result['score']}, filter: '{best_result['filter_used']}')")

                # Debug the field extraction
                sample_entries = self._extract_arp_entries_from_textfsm(best_result)
                if sample_entries:
                    logger.debug(f"Extracted {len(sample_entries)} entries")
                    logger.debug(f"Sample extracted entry: {sample_entries[0]}")
                else:
                    logger.warning("TextFSM parsing succeeded but field extraction failed")

                return best_result
            else:
                logger.warning(
                    f"No suitable TextFSM template found (best score: {best_result['score'] if best_result else 0})")

        except Exception as e:
            logger.error(f"TextFSM parsing failed: {e}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")

        return None

    def _normalize_mac_address(self, mac: str) -> str:
        """Normalize MAC address to standard format"""
        if not mac:
            return ""

        # Remove all non-alphanumeric characters
        clean_mac = re.sub(r'[^a-fA-F0-9]', '', mac.strip())

        # Validate length
        if len(clean_mac) != 12:
            return ""

        # Convert to lowercase and add colons
        return ':'.join([clean_mac[i:i + 2] for i in range(0, 12, 2)]).lower()

    def _validate_ip_address(self, ip: str) -> bool:
        """Validate IP address"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def _extract_arp_entries_from_textfsm(self, textfsm_result: Dict) -> List[Dict]:
        """Extract ARP entries from TextFSM results"""
        entries = []
        parsed_data = textfsm_result.get('parsed_data', [])

        if not parsed_data:
            return entries

        # Handle both list of dicts and list of lists
        for row in parsed_data:
            if isinstance(row, dict):
                # Direct dictionary format
                entry = self._extract_arp_entry_from_dict(row)
            elif isinstance(row, list):
                # List format - need to map to common fields
                entry = self._extract_arp_entry_from_list(row, textfsm_result.get('template_name', ''))
            else:
                continue

            if entry:
                entries.append(entry)

        return entries

    def _extract_arp_entry_from_dict(self, row: Dict) -> Optional[Dict]:
        """Extract ARP entry from dictionary row with vendor-specific field mapping"""
        entry = {}

        # IP Address - handle multiple field names
        ip_fields = ['IP_ADDRESS', 'ADDRESS']  # ADDRESS is used in the 'show ip arp' template
        for field in ip_fields:
            if field in row and row[field]:
                ip_addr = str(row[field]).strip()
                if self._validate_ip_address(ip_addr):
                    entry['ip_address'] = ip_addr
                    break

        # MAC Address - handle multiple field names
        mac_fields = ['MAC_ADDRESS', 'HARDWARE_ADDR']  # HARDWARE_ADDR is used in the 'show ip arp' template
        for field in mac_fields:
            if field in row and row[field]:
                mac_addr = str(row[field]).strip()
                normalized_mac = self._normalize_mac_address(mac_addr)
                if normalized_mac:
                    entry['mac_address'] = normalized_mac
                    entry['mac_address_raw'] = mac_addr
                    break

        # Interface - INTERFACE (most vendors) or PORT (HP)
        interface_value = None
        if 'INTERFACE' in row and row['INTERFACE']:
            interface_value = str(row['INTERFACE']).strip()
        elif 'PORT' in row and row['PORT']:
            interface_value = str(row['PORT']).strip()

        if interface_value:
            entry['interface_name'] = interface_value

        # Age - present in most vendors except HP
        if 'AGE' in row and row['AGE']:
            entry['age'] = str(row['AGE']).strip()

        # Entry Type/Flags - different field names per vendor
        type_value = None
        if 'TYPE' in row and row['TYPE']:  # Cisco IOS, HP
            type_value = str(row['TYPE']).strip().lower()
        elif 'FLAGS' in row and row['FLAGS']:  # Juniper
            type_value = str(row['FLAGS']).strip().lower()
        elif 'PROTOCOL' in row and row['PROTOCOL']:  # Cisco IOS protocol field
            protocol = str(row['PROTOCOL']).strip().lower()
            # Map protocol to entry type
            if protocol == 'internet':
                type_value = 'dynamic'
            else:
                type_value = protocol

        if type_value:
            entry['entry_type'] = type_value
        else:
            entry['entry_type'] = 'dynamic'  # Default

        # VRF Context - Arista specific
        if 'VRF' in row and row['VRF']:
            entry['vrf'] = str(row['VRF']).strip()

        # Must have at least IP and MAC
        if 'ip_address' in entry and 'mac_address' in entry:
            return entry

        return None

    def _extract_arp_entry_from_list(self, row: List, template_name: str) -> Optional[Dict]:
        """Extract ARP entry from list row based on template"""
        # This would need template-specific logic
        # For now, use a generic approach
        if len(row) < 2:
            return None

        entry = {}

        # Try to find IP and MAC in the row
        for item in row:
            if not item:
                continue

            item_str = str(item).strip()

            if not entry.get('ip_address') and self._validate_ip_address(item_str):
                entry['ip_address'] = item_str
            elif not entry.get('mac_address'):
                normalized_mac = self._normalize_mac_address(item_str)
                if normalized_mac:
                    entry['mac_address'] = normalized_mac
                    entry['mac_address_raw'] = item_str

        if 'ip_address' in entry and 'mac_address' in entry:
            return entry

        return None

    def get_arp_captures(self, processed_only: bool = False, device_filter: str = None) -> List[Dict]:
        """Get ARP captures from assets database"""
        try:
            conn = sqlite3.connect(self.assets_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query the v_capture_details view for ARP captures
            query = """
                SELECT * FROM v_capture_details 
                WHERE capture_type = 'arp'
                AND extraction_success = 1
                AND file_path IS NOT NULL
            """
            params = []

            # Add device name filter
            if device_filter:
                query += " AND (device_name LIKE ? OR device_normalized_name LIKE ?)"
                params.extend([f"%{device_filter}%", f"%{device_filter}%"])

            if processed_only:
                # Only get files that haven't been processed yet
                # This would require tracking in arp_cat.db
                pass

            query += " ORDER BY capture_timestamp DESC"

            cursor.execute(query, params)
            captures = [dict(row) for row in cursor.fetchall()]

            conn.close()
            logger.info(f"Found {len(captures)} ARP captures to process" +
                        (f" (filtered by '{device_filter}')" if device_filter else ""))
            return captures

        except sqlite3.Error as e:
            logger.error(f"Error querying assets database: {e}")
            return []

    def load_arp_capture(self, capture: Dict) -> int:
        """Load a single ARP capture into arp_cat.db"""
        file_path = capture.get('file_path')
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"ARP file not found: {file_path}")
            return 0

        logger.info(f"Processing ARP capture: {file_path}")

        # Read the file content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return 0

        if not content.strip():
            logger.warning(f"Empty ARP file: {file_path}")
            return 0

        # Extract device and context information
        device_info = {
            'hostname': capture.get('device_name', capture.get('device_normalized_name', 'unknown')),
            'device_type': capture.get('device_type_name'),
            'vendor': capture.get('vendor_name'),
            'model': capture.get('device_model'),
            'site_code': capture.get('site_code'),
            'management_ip': capture.get('management_ip')
        }

        # Parse ARP entries using TextFSM only
        arp_entries = []
        vendor = capture.get('vendor_name', '')

        if self.textfsm_engine:
            textfsm_result = self._parse_arp_with_textfsm(
                content, vendor, capture.get('device_type_name', '')
            )

            if textfsm_result:
                arp_entries = self._extract_arp_entries_from_textfsm(textfsm_result)
                logger.info(f"TextFSM extracted {len(arp_entries)} ARP entries from {file_path}")
            else:
                logger.warning(f"TextFSM found no matching templates for {file_path} (vendor: {vendor})")
                return 0
        else:
            logger.error("TextFSM engine not available")
            return 0

        if not arp_entries:
            logger.warning(f"No ARP entries extracted from {file_path}")
            return 0

        # Group entries by VRF/context
        context_groups = self._group_entries_by_context(arp_entries, vendor)

        # Store in arp_cat.db
        total_entries_loaded = 0
        try:
            with ArpCatUtil(self.arp_cat_db_path) as arp_util:
                # Create device
                device_id = arp_util.get_or_create_device(**device_info)

                # Process each context group
                for context_name, entries in context_groups.items():
                    # Determine context type based on vendor
                    context_type = self._get_context_type(vendor, context_name)

                    context_info = {
                        'context_name': context_name,
                        'context_type': context_type,
                        'description': f"ARP table from {capture.get('capture_timestamp')}"
                    }

                    context_id = arp_util.get_or_create_context(device_id, **context_info)

                    # Create snapshot for this context
                    capture_timestamp = self._normalize_timestamp(capture.get('capture_timestamp'))

                    snapshot_id = arp_util.create_snapshot(
                        device_id, context_id, capture_timestamp,
                        source_file=file_path,
                        source_command='show arp',
                        processing_status='processed'
                    )

                    # Add ARP entries for this context
                    entries_loaded = 0
                    for entry in entries:
                        try:
                            arp_util.add_arp_entry(
                                device_id, context_id,
                                entry['ip_address'],
                                entry['mac_address'],
                                interface_name=entry.get('interface_name'),
                                entry_type=entry.get('entry_type', 'dynamic'),
                                age=entry.get('age'),
                                capture_timestamp=capture_timestamp,
                                source_file=file_path,
                                source_command='show arp'
                            )
                            entries_loaded += 1
                        except Exception as e:
                            logger.warning(f"Error adding ARP entry {entry}: {e}")

                    total_entries_loaded += entries_loaded
                    logger.info(f"Loaded {entries_loaded} entries for context '{context_name}'")

        except Exception as e:
            logger.error(f"Error storing ARP data for {file_path}: {e}")
            return 0

        logger.info(f"Total loaded {total_entries_loaded} ARP entries from {file_path}")
        return total_entries_loaded

    def _group_entries_by_context(self, arp_entries: List[Dict], vendor: str) -> Dict[str, List[Dict]]:
        """Group ARP entries by VRF/context"""
        context_groups = {}
        vendor_lower = vendor.lower() if vendor else ''

        for entry in arp_entries:
            # Extract context from entry
            context_name = 'default'

            # Arista uses VRF field
            if 'arista' in vendor_lower and 'vrf' in entry:
                context_name = entry['vrf']
                del entry['vrf']  # Remove from entry data

            # Other vendors might embed VRF in interface name or other fields
            # This can be extended as needed

            if context_name not in context_groups:
                context_groups[context_name] = []

            context_groups[context_name].append(entry)

        return context_groups

    def _get_context_type(self, vendor: str, context_name: str) -> str:
        """Determine context type based on vendor and context name"""
        vendor_lower = vendor.lower() if vendor else ''

        # Vendor-specific context type mapping
        if 'arista' in vendor_lower or 'cisco' in vendor_lower:
            return 'vrf'
        elif 'juniper' in vendor_lower:
            return 'routing-instance'
        elif 'fortinet' in vendor_lower:
            return 'vdom'
        elif 'paloalto' in vendor_lower:
            return 'vsys'
        else:
            return 'vrf'  # Default

    def _normalize_timestamp(self, timestamp: str) -> str:
        """Normalize timestamp to ISO format"""
        if not timestamp:
            return datetime.now().isoformat()

        try:
            # Try to parse various timestamp formats
            if 'T' in timestamp:
                # Already ISO format
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                # Try common formats
                try:
                    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    dt = datetime.strptime(timestamp, '%Y-%m-%d')

            return dt.isoformat()
        except:
            return datetime.now().isoformat()

    def load_all_captures(self, max_files: int = None, device_filter: str = None) -> Dict[str, int]:
        """Load all ARP captures from assets database"""
        captures = self.get_arp_captures(device_filter=device_filter)

        if max_files:
            captures = captures[:max_files]

        stats = {
            'files_processed': 0,
            'files_skipped': 0,
            'total_entries': 0,
            'errors': 0
        }

        logger.info(f"Processing {len(captures)} captures" +
                    (f" (max {max_files})" if max_files else "") +
                    (f" (filtered by '{device_filter}')" if device_filter else ""))

        for i, capture in enumerate(captures, 1):
            logger.info(f"\n--- Processing {i}/{len(captures)}: {capture.get('device_name')} ---")
            logger.info(f"File: {capture.get('file_path')}")
            logger.info(f"Vendor: {capture.get('vendor_name')}")
            logger.info(f"Device Type: {capture.get('device_type_name')}")

            try:
                entries_count = self.load_arp_capture(capture)
                if entries_count > 0:
                    stats['files_processed'] += 1
                    stats['total_entries'] += entries_count
                    logger.info(f"✓ SUCCESS: Loaded {entries_count} entries")
                else:
                    stats['files_skipped'] += 1
                    logger.warning(f"✗ SKIPPED: No entries loaded")
            except Exception as e:
                logger.error(f"✗ ERROR: {e}")
                stats['errors'] += 1

        logger.info(f"\nProcessing complete: {stats}")
        return stats


def main():
    """Main CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description="Load ARP captures into arp_cat.db")
    parser.add_argument("--assets-db", default="assets.db", help="Path to assets database")
    parser.add_argument("--arp-db", default="arp_cat.db", help="Path to ARP cat database")
    parser.add_argument("--textfsm-db", default="Anguis/tfsm_templates.db", help="Path to TextFSM templates")
    parser.add_argument("--max-files", type=int, help="Maximum files to process")
    parser.add_argument("--device-filter", help="Filter by device name (partial match)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--debug", action="store_true", help="Debug level logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    # Initialize loader
    loader = ArpCaptureLoader(
        assets_db_path=args.assets_db,
        arp_cat_db_path=args.arp_db,
        textfsm_db_path=args.textfsm_db
    )

    # Load captures
    stats = loader.load_all_captures(max_files=args.max_files, device_filter=args.device_filter)

    print(f"\nARP Capture Loading Complete:")
    print(f"  Files processed: {stats['files_processed']}")
    print(f"  Files skipped: {stats['files_skipped']}")
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    main()