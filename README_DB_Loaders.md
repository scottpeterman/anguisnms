# Network Asset Database Loaders

This directory contains database loading utilities for populating the network asset management database from discovery pipeline outputs.

## Overview

The database loaders process two main types of data:

1. **Fingerprint Loader** (`db_load_fingerprints.py`) - Loads device fingerprint JSON files from the discovery pipeline
2. **Capture Loader** (`db_load_captures.py`) - Loads operational data capture files (configs, version info, etc.)

Both loaders support incremental updates and are designed for daily operational use.

## Prerequisites

- SQLite database created with the network asset management schema
- Python 3.8+ with required dependencies
- Fingerprint JSON files from the discovery pipeline
- Capture files organized by type in subdirectories

## Installation

```bash
pip install click sqlite3 pathlib
```

## Fingerprint Loader

### Purpose
Loads device fingerprint JSON files containing TextFSM-parsed device information into the database. Handles complex scenarios like Cisco switch stacks with multiple serials.

### Key Features
- **Stack Detection**: Automatically parses comma-separated serials and models for switch stacks
- **Site Code Extraction**: Derives site codes from hostnames using pattern matching
- **Vendor/Device Type Mapping**: Maps fingerprint data to normalized vendor and device type tables
- **Incremental Updates**: Supports daily re-runs with proper upserts
- **Audit Trail**: Records fingerprint extraction metadata for tracking

### Usage

#### Process All Fingerprints
```bash
python db_load_fingerprints.py --fingerprints-dir fingerprints --db-path assets.db --verbose
```

#### Process Single File
```bash
python db_load_fingerprints.py --single-file fingerprints/device.json --db-path assets.db --verbose
```

#### Command Options
- `--db-path`: Path to SQLite database (default: assets.db)
- `--fingerprints-dir`: Directory containing fingerprint JSON files (default: fingerprints)
- `--single-file`: Process a single fingerprint file
- `--verbose`: Enable verbose logging

### Input Format
Expected fingerprint JSON format:
```json
{
  "hostname": "ush-k1-swl-01",
  "host": "10.42.79.2",
  "model": "C9300-48UXM, C9300-48UXM, C9300-48UXM",
  "version": "17.9.4a",
  "serial_number": "FCW2425G0BB, FJC2422E0NW, FJC2422E0NB",
  "additional_info": {
    "vendor": "Cisco",
    "netmiko_driver": "cisco_ios"
  },
  "command_outputs": {
    "show version_textfsm": {
      "records": [...],
      "STACK_MEMBERS": [...]
    }
  },
  "success": true
}
```

### Stack Handling
The loader automatically detects and processes switch stacks:

- **Comma-separated serials**: `"FCW2425G0BB, FJC2422E0NW, FJC2422E0NB"`
- **TextFSM stack data**: Parses `STACK_MEMBERS` arrays with individual switch details
- **Database population**: Creates individual `stack_members` records with proper indexing

### Site Code Extraction
Automatically extracts site codes from hostnames using patterns:
- `site-device-01` → `SITE`
- `abc-core-switch` → `ABC`
- Falls back to "UNKNOWN" for IP-only devices

## Capture Loader

### Purpose
Loads network device capture files (configs, version info, interface status, etc.) into the database with current/archive pattern for historical tracking.

### Key Features
- **31 Capture Types**: Supports all standard network capture types
- **Current/Archive Pattern**: Maintains current state with 30-day archive retention
- **Filename Parsing**: Extracts device names and capture types from filenames
- **Success Analysis**: Determines capture success based on file size and content
- **Batch Processing**: Handles thousands of files with progress tracking

### Usage

#### Process All Captures
```bash
python db_load_captures.py --captures-dir capture --db-path assets.db --verbose
```

#### Process Specific Types
```bash
python db_load_captures.py --captures-dir capture --capture-types "configs,version,interface-status" --db-path assets.db
```

#### Archive Cleanup
```bash
python db_load_captures.py --cleanup-archives --archive-days 30 --db-path assets.db
```

#### Command Options
- `--db-path`: Path to SQLite database (default: assets.db)
- `--captures-dir`: Directory containing capture subdirectories (default: capture)
- `--capture-types`: Comma-separated list of specific types to process
- `--single-file`: Process a single capture file
- `--cleanup-archives`: Clean up old archive records
- `--archive-days`: Days of archives to keep (default: 30)
- `--verbose`: Enable verbose logging

### Directory Structure
Expected capture directory organization:
```
capture/
├── configs/
│   ├── SITE-DEVICE-01_running-config.txt
│   └── SITE-DEVICE-02_running-config.txt
├── version/
│   ├── SITE-DEVICE-01_version.txt
│   └── SITE-DEVICE-02_version.txt
├── interface-status/
│   ├── SITE-DEVICE-01_int-status.txt
│   └── SITE-DEVICE-02_int-status.txt
└── [29 other capture types]/
    └── [capture files]
```

### Supported Capture Types
```
arp, authentication, authorization, bgp-neighbor, bgp-summary, bgp-table, 
bgp-table-detail, cdp, cdp-detail, configs, console, eigrp-neighbor, 
int-status, interface-status, inventory, ip_ssh, lldp, lldp-detail, mac, 
ntp_status, ospf-neighbor, port-channel, routes, snmp_server, syslog, 
tacacs, version
```

### Filename Conventions
The loader supports multiple filename patterns:
- `SITE-DEVICE-NAME_capture-type.txt`
- `SITE-DEVICE-NAME.capture-type.txt`
- Files organized in subdirectories by capture type

### Current/Archive Pattern
- **Current Table**: One record per device/capture_type (latest state)
- **Archive Table**: Historical captures with 30-day retention
- **Automatic Archiving**: Old captures moved to archive before updates

## Database Utilities

Additional utility script for database management:

```bash
# View database statistics
python db_utilities.py stats --db-path assets.db

# Check for discovery gaps
python db_utilities.py gaps --db-path assets.db

# Analyze capture success rates
python db_utilities.py success-rates --db-path assets.db

# Site coverage report
python db_utilities.py coverage --db-path assets.db

# Export inventory
python db_utilities.py export --output inventory.json --db-path assets.db

# Clean up orphaned data
python db_utilities.py cleanup --dry-run --db-path assets.db

# Optimize database
python db_utilities.py optimize --db-path assets.db
```

## Daily Workflow

Recommended daily processing sequence:

```bash
# 1. Load new fingerprints (handles device updates)
python db_load_fingerprints.py --fingerprints-dir fingerprints --db-path assets.db --verbose

# 2. Load new captures (archives previous versions)  
python db_load_captures.py --captures-dir capture --db-path assets.db --verbose

# 3. Generate daily reports
python db_utilities.py stats --db-path assets.db
python db_utilities.py gaps --db-path assets.db

# 4. Weekly maintenance
python db_utilities.py cleanup --db-path assets.db
python db_utilities.py optimize --db-path assets.db
```

## Performance Characteristics

### Fingerprint Loader
- **~400 devices**: 30-60 seconds processing time
- **Stack devices**: Automatic detection and parsing
- **Memory usage**: Low (processes files sequentially)

### Capture Loader  
- **5,000+ files**: 5-10 minutes processing time
- **Success rate**: Typically 50-60% (network conditions dependent)
- **Throughput**: ~15-20 files per second

### Database Growth
- **Core tables**: ~50MB for 2,000 devices
- **Current captures**: ~200MB (31 types × 2,000 devices)
- **Archives**: ~6GB annually with 30-day retention

## Troubleshooting

### Common Issues

#### Device Not Found for Capture Files
```
Device not found for file: capture/configs/device-name.txt
```
**Solution**: Run fingerprint loader first to create device records

#### Stack Count Not Updating
```sql
-- Check stack members
SELECT * FROM stack_members WHERE device_id = X;

-- Manually fix if needed
UPDATE devices SET stack_count = (
    SELECT COUNT(*) FROM stack_members WHERE device_id = X
) WHERE id = X;
```

#### Low Capture Success Rate
```bash
# Analyze by type and vendor
python db_utilities.py success-rates --db-path assets.db

# Check specific failures
python db_load_captures.py --single-file problem_file.txt --verbose
```

### Logging
Both loaders support verbose logging:
- **INFO**: Progress and summary information
- **DEBUG**: Detailed processing information  
- **ERROR**: Failures and issues

## Schema Dependencies

The loaders require these database tables:
- `sites`, `vendors`, `device_types`, `device_roles`
- `devices`, `device_serials`, `stack_members`
- `fingerprint_extractions`
- `device_captures_current`, `device_captures_archive`

Refer to the main database schema documentation for table structures and relationships.

## Integration Notes

### Pipeline Integration
These loaders are designed to integrate with:
- Network discovery pipelines (topology.json → sessions.yaml → fingerprints)
- Capture automation (batch command execution → capture files)
- Reporting systems (database → analysis tools)

### API Compatibility
Database structure supports integration with:
- Web dashboards and monitoring tools
- ITSM systems via JSON exports
- Automation frameworks via direct database access

### Backup Considerations
- Regular database backups recommended before bulk loads
- Archive table cleanup affects historical data retention
- Consider separate backup strategy for raw capture files