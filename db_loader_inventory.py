#!/usr/bin/env python3
"""
Inventory Loader - Phase 1: Basic Chassis Parsing

Parses inventory captures from assets.db and populates the components table.
Uses TextFSM templates only - fails explicitly when templates don't match.
"""

import os
import sqlite3
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Import TextFSM engine
try:
    from tfsm_fire import TextFSMAutoEngine

    TEXTFSM_AVAILABLE = True
except ImportError:
    TEXTFSM_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class InventoryLoader:
    """Loads inventory captures and populates components table"""

    # Minimum acceptable template match score
    MINIMUM_SCORE = 20

    def __init__(self, assets_db_path: str = "assets.db",
                 textfsm_db_path: str = "Anguis/tfsm_templates.db"):
        self.assets_db_path = assets_db_path
        self.textfsm_db_path = textfsm_db_path
        self.textfsm_engine = None

        if not TEXTFSM_AVAILABLE:
            raise ImportError("TextFSM not available - cannot proceed")

        self._initialize_textfsm()

    def _initialize_textfsm(self):
        """Initialize TextFSM engine"""
        if not os.path.exists(self.textfsm_db_path):
            raise FileNotFoundError(f"TextFSM templates not found: {self.textfsm_db_path}")

        self.textfsm_engine = TextFSMAutoEngine(self.textfsm_db_path, verbose=False)
        logger.info(f"✓ TextFSM initialized: {self.textfsm_db_path}")

    def _create_vendor_filter(self, vendor: str) -> List[str]:
        """Create TextFSM filters for inventory commands"""
        if not vendor:
            return ['show_inventory']

        vendor_lower = vendor.lower()

        # EXACT template names from your database
        vendor_filters = {
            'cisco': [
                'cisco_ios_show_inventory',
                'cisco_nxos_show_inventory'
            ],
            'arista': [
                'arista_eos_show_inventory',
                'arista_eos_show_version'  # Arista includes inventory in version output
            ],
            'hewlett': [
                'hp_procurve_show_system',
                'hp_comware_display_device'
            ],
            'procurve': [
                'hp_procurve_show_system'
            ],
            'aruba': [
                'aruba_os_show_system'
            ]
        }

        filters = []
        for key, filter_list in vendor_filters.items():
            if key in vendor_lower:
                filters.extend(filter_list)
                logger.debug(f"Added {len(filter_list)} filters for vendor key '{key}'")
                break

        # Generic fallback
        filters.append('show_inventory')

        return filters

    def _parse_inventory_with_textfsm(self, content: str, vendor: str,
                                      device_type: str = None) -> Optional[Dict]:
        """Parse inventory using TextFSM - NO fallback parsing"""
        if not self.textfsm_engine:
            logger.error("TextFSM engine not available")
            return None

        filter_attempts = self._create_vendor_filter(vendor)
        logger.info(f"Trying TextFSM filters for vendor '{vendor}': {filter_attempts}")

        best_result = None
        best_score = 0

        for i, filter_string in enumerate(filter_attempts, 1):
            logger.debug(f"Attempt {i}/{len(filter_attempts)}: '{filter_string}'")

            try:
                result = self.textfsm_engine.find_best_template(content, filter_string)

                if len(result) == 4:
                    template, parsed_data, score, template_content = result
                elif len(result) == 3:
                    template, parsed_data, score = result
                    template_content = None
                else:
                    logger.debug(f"  Unexpected result format: {len(result)} items")
                    continue

                logger.debug(
                    f"  Template: '{template}' | Score: {score} | Records: {len(parsed_data) if parsed_data else 0}")

                if parsed_data:
                    logger.debug(f"  Sample record: {parsed_data[0]}")

                if score > best_score and parsed_data:
                    best_score = score
                    best_result = {
                        'template_name': template,
                        'score': score,
                        'parsed_data': parsed_data,
                        'filter_used': filter_string,
                        'template_content': template_content
                    }

                    logger.info(f"  ✓ NEW BEST: {template} (score: {score}, records: {len(parsed_data)})")

                    if score > 70:
                        logger.info(f"  High confidence match - stopping search")
                        break

            except Exception as e:
                logger.debug(f"  Filter '{filter_string}' failed: {e}")
                continue

        # STRICT: Reject low-confidence matches
        if best_result and best_result['score'] >= self.MINIMUM_SCORE:
            logger.info(
                f"✓ ACCEPTED: Template '{best_result['template_name']}' "
                f"(score: {best_result['score']}, filter: '{best_result['filter_used']}')"
            )
            return best_result
        else:
            score = best_result['score'] if best_result else 0
            logger.warning(
                f"✗ REJECTED: Best score {score} < minimum {self.MINIMUM_SCORE}. "
                f"Template needs improvement for vendor '{vendor}'"
            )
            return None

    def _extract_components_from_textfsm(self, textfsm_result: Dict,
                                         device_info: Dict) -> List[Dict]:
        """Extract component data from TextFSM results"""
        components = []
        parsed_data = textfsm_result.get('parsed_data', [])

        if not parsed_data:
            return components

        # Field name mappings based on your templates
        field_mappings = {
            # Common across vendors
            'name': ['NAME', 'name'],
            'description': ['DESCR', 'description', 'DESCRIPTION'],
            'serial': ['SN', 'serial', 'SERIAL_NUMBER'],
            'model': ['PID', 'model', 'MODEL'],
            'version': ['VID', 'version', 'VERSION'],
            'position': ['PORT', 'SLOT', 'position', 'POSITION']
        }

        for row in parsed_data:
            if not isinstance(row, dict):
                logger.warning(f"Skipping non-dict row: {type(row)}")
                continue

            component = self._map_fields(row, field_mappings)

            if component:
                # Determine component type from name/description
                component['type'] = self._determine_component_type(component)
                component['extraction_source'] = 'inventory_capture'
                component['extraction_confidence'] = textfsm_result['score'] / 100.0

                components.append(component)

        return components

    def _map_fields(self, row: Dict, field_mappings: Dict) -> Optional[Dict]:
        """Map TextFSM fields to component fields"""
        component = {}

        # Extract each field using priority mapping
        for target_field, source_fields in field_mappings.items():
            for source_field in source_fields:
                if source_field in row and row[source_field]:
                    value = str(row[source_field]).strip()
                    if value and value not in ['-', 'N/A', '']:
                        component[target_field] = value
                        break

        # CRITICAL FIX: If no name, use description as name
        if not component.get('name') and component.get('description'):
            component['name'] = component['description']

        # Must have at least name (after fallback)
        if not component.get('name'):
            return None

        # Set have_sn flag
        component['have_sn'] = bool(component.get('serial'))

        return component
    def _determine_component_type(self, component: Dict) -> str:
        """Determine component type from name/description"""
        text = (component.get('name', '') + ' ' + component.get('description', '')).lower()

        type_keywords = {
            'chassis': ['chassis', 'stack', 'switch '],
            'module': ['module', 'linecard', 'line card'],
            'psu': ['power supply', 'psu', 'power-supply'],
            'fan': ['fan', 'cooling'],
            'transceiver': ['transceiver', 'sfp', 'qsfp', 'gbic'],
            'supervisor': ['supervisor', 'sup', 'management'],
        }

        for comp_type, keywords in type_keywords.items():
            if any(kw in text for kw in keywords):
                return comp_type

        return 'unknown'

    def get_inventory_captures(self, device_filter: str = None) -> List[Dict]:
        """Get inventory captures from assets database"""
        try:
            conn = sqlite3.connect(self.assets_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT * FROM v_capture_details 
                WHERE capture_type = 'inventory'
                AND extraction_success = 1
                AND file_path IS NOT NULL
            """
            params = []

            if device_filter:
                query += " AND (device_name LIKE ? OR device_normalized_name LIKE ?)"
                params.extend([f"%{device_filter}%", f"%{device_filter}%"])

            query += " ORDER BY capture_timestamp DESC"

            cursor.execute(query, params)
            captures = [dict(row) for row in cursor.fetchall()]

            conn.close()
            logger.info(
                f"Found {len(captures)} inventory captures" +
                (f" (filtered by '{device_filter}')" if device_filter else "")
            )
            return captures

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return []

    def load_inventory_capture(self, capture: Dict) -> int:
        """Load a single inventory capture and populate components"""
        file_path = capture.get('file_path')
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return 0

        logger.info(f"Processing: {file_path}")

        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return 0

        if not content.strip():
            logger.warning(f"Empty file: {file_path}")
            return 0

        # Device info
        device_info = {
            'device_id': capture.get('device_id'),
            'hostname': capture.get('device_name'),
            'vendor': capture.get('vendor_name'),
            'model': capture.get('device_model'),
            'site_code': capture.get('site_code')
        }

        # Parse with TextFSM
        textfsm_result = self._parse_inventory_with_textfsm(
            content,
            capture.get('vendor_name', ''),
            capture.get('device_type_name', '')
        )

        if not textfsm_result:
            logger.warning(f"✗ PARSING FAILED: {file_path}")
            logger.warning(f"  Vendor: {capture.get('vendor_name')}")
            logger.warning(f"  Action: Create/fix TextFSM template for this vendor")
            return 0

        # Extract components
        components = self._extract_components_from_textfsm(textfsm_result, device_info)

        if not components:
            logger.warning(f"No components extracted from {file_path}")
            return 0

        # Store in database
        components_loaded = self._store_components(device_info['device_id'], components)

        logger.info(f"✓ Loaded {components_loaded} components from {file_path}")
        return components_loaded

    def _store_components(self, device_id: int, components: List[Dict]) -> int:
        """Store components in database"""
        try:
            conn = sqlite3.connect(self.assets_db_path)
            cursor = conn.cursor()

            # Clear existing components for this device
            cursor.execute("DELETE FROM components WHERE device_id = ?", (device_id,))

            # Insert new components
            count = 0
            for comp in components:
                cursor.execute("""
                    INSERT INTO components (
                        device_id, name, description, serial, position,
                        have_sn, type, subtype, extraction_source, extraction_confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    device_id,
                    comp.get('name'),
                    comp.get('description'),
                    comp.get('serial'),
                    comp.get('position'),
                    comp.get('have_sn', False),
                    comp.get('type'),
                    comp.get('subtype'),
                    comp.get('extraction_source'),
                    comp.get('extraction_confidence')
                ))
                count += 1

            conn.commit()
            conn.close()
            return count

        except sqlite3.Error as e:
            logger.error(f"Database error storing components: {e}")
            return 0

    def load_all_captures(self, max_files: int = None, device_filter: str = None) -> Dict[str, int]:
        """Load all inventory captures"""
        captures = self.get_inventory_captures(device_filter=device_filter)

        if max_files:
            captures = captures[:max_files]

        stats = {
            'files_processed': 0,
            'files_failed': 0,
            'total_components': 0,
            'template_failures': 0
        }

        logger.info(f"Processing {len(captures)} inventory captures")

        for i, capture in enumerate(captures, 1):
            progress = (i / len(captures)) * 100
            logger.info(f"\n--- {i}/{len(captures)} ({progress:.1f}%): {capture.get('device_name')} ---")
            logger.info(f"Vendor: {capture.get('vendor_name')}")

            try:
                count = self.load_inventory_capture(capture)
                if count > 0:
                    stats['files_processed'] += 1
                    stats['total_components'] += count
                else:
                    stats['files_failed'] += 1
                    if "Template needs improvement" in str(count):
                        stats['template_failures'] += 1
            except Exception as e:
                logger.error(f"✗ ERROR: {e}")
                stats['files_failed'] += 1

        logger.info(f"\n{'=' * 70}")
        logger.info("PROCESSING COMPLETE")
        logger.info(f"{'=' * 70}")
        logger.info(f"Files processed:    {stats['files_processed']}")
        logger.info(f"Files failed:       {stats['files_failed']}")
        logger.info(f"Template failures:  {stats['template_failures']}")
        logger.info(f"Total components:   {stats['total_components']}")

        return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Load inventory captures into components table")
    parser.add_argument("--assets-db", default="assets.db", help="Path to assets database")
    parser.add_argument("--textfsm-db", default="Anguis/tfsm_templates.db", help="Path to TextFSM templates")
    parser.add_argument("--max-files", type=int, help="Maximum files to process")
    parser.add_argument("--device-filter", help="Filter by device name")
    parser.add_argument("--debug", action="store_true", help="Debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        loader = InventoryLoader(
            assets_db_path=args.assets_db,
            textfsm_db_path=args.textfsm_db
        )

        stats = loader.load_all_captures(
            max_files=args.max_files,
            device_filter=args.device_filter
        )

        print(f"\nInventory Loading Summary:")
        print(f"  Processed: {stats['files_processed']}")
        print(f"  Failed: {stats['files_failed']}")
        print(f"  Components loaded: {stats['total_components']}")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())