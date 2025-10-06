# Anguis Network Management - Maintenance Utilities

Complete backup, restore, and reset utilities for managing your Anguis environment.

## Overview

Three complementary utilities for lifecycle management:

- **backup.py** - Create compressed archives of databases and artifacts
- **restore.py** - Restore complete environment from backup archives  
- **reset.py** - Reset environment to fresh installation state

## Installation

Place these scripts in the Anguis project root directory:

```bash
anguis/
├── backup.py           # Backup utility
├── restore.py          # Restore utility
├── reset.py            # Reset utility
├── db_init.py          # Database initialization
├── arp_cat_init_schema.py
├── app/                # Flask web application
├── pcng/               # Primary data directory
│   ├── capture/        # Network device captures (28 types)
│   ├── fingerprints/   # Device fingerprint data
│   ├── maps/           # Topology visualizations
│   └── ...
└── diffs/              # Configuration change tracking
```

All scripts require Python 3.8+ with standard library only (no additional dependencies).

## Project Structure Note

Anguis stores operational data in the `pcng/` subdirectory. The backup utilities handle this structure automatically, preserving the complete directory hierarchy during backup and restore operations.

## Backup Utility

### Basic Usage

```bash
# Full backup (includes everything)
python backup.py --output ./backups

# Metadata-only backup (excludes large capture files)
python backup.py --output ./backups --no-captures

# Include log files
python backup.py --output ./backups --include-logs
```

### What Gets Backed Up

**Always included:**
- `assets.db` - Main database with devices, sites, components, etc.
- `arp_cat.db` - ARP/MAC address tracking database
- `pcng/fingerprints/` - Device fingerprint data (~443 files, ~3 MB)
- `pcng/maps/` - Network topology visualizations (~262 files, ~130 MB)
- `diffs/` - Configuration change diffs (~104 files, <1 MB)

**Optional (can be large):**
- `pcng/capture/` - Raw configuration captures (28 types: configs, inventory, arp, routing, etc.)
  - Typical: 10,000+ files, 180-200 MB uncompressed
  - Excluded with `--no-captures` flag
- `logs/` - Application logs (excluded by default, use `--include-logs`)

**Typical backup sizes:**
- Metadata-only (no captures): ~15-20 MB compressed
- Full backup (with captures): ~50-80 MB compressed
- Size scales with number of devices and capture types

### Backup Archive Structure

```
anguis_backup_20251005_180309.tar.gz (58 MB compressed)
└── anguis_backup_20251005_180309/
    ├── backup_manifest.json          # Metadata and checksums
    ├── assets.db                     # Main database (10 MB)
    ├── arp_cat.db                    # ARP database (3 MB)
    ├── diffs/                        # Change tracking (104 files)
    ├── pcng/
    │   ├── fingerprints/             # Device fingerprints (443 files)
    │   ├── maps/                     # Network maps (262 files, 130 MB)
    │   └── capture/                  # Device captures (10,229 files, 189 MB)
    │       ├── arp/
    │       ├── authentication/
    │       ├── configs/
    │       ├── inventory/
    │       ├── lldp/
    │       ├── routes/
    │       └── ... (28 capture types total)
    └── sessions/ (if exists)
```

**Compression efficiency:** The above example shows ~335 MB of raw data compressed to 58 MB (17% of original size).

### Backup Manifest

Each backup includes a manifest with:
- Timestamp and schema version
- Database table record counts
- File checksums (SHA256)
- Directory statistics
- Backup configuration

Example manifest excerpt:
```json
{
  "backup_metadata": {
    "timestamp": "2025-10-05T17:30:00",
    "schema_version": "1.0.0",
    "include_captures": true
  },
  "databases": {
    "assets.db": {
      "size_mb": 45.2,
      "tables": {
        "devices": 358,
        "components": 1684,
        "sites": 53
      }
    }
  },
  "checksums": {
    "assets.db": "a1b2c3d4..."
  }
}
```

## Restore Utility

### Basic Usage

```bash
# Restore with confirmation prompt
python restore.py --archive ./backups/anguis_backup_20251005_173000.tar.gz

# Force restore without prompts
python restore.py --archive backup.tar.gz --force

# Restore without creating safety backup
python restore.py --archive backup.tar.gz --skip-safety-backup
```

### Restore Process

1. **Validation** - Extracts and validates archive integrity
2. **Safety Backup** - Creates pre-restore backup of current state
3. **Confirmation** - Prompts for user confirmation (unless `--force`)
4. **Clear State** - Removes current databases and artifacts
5. **Restore Data** - Copies databases and artifacts from backup
6. **Verification** - Validates record counts against manifest

### Safety Backups

Before each restore, a safety backup is created:

```
safety_backups/
└── pre_restore_20251005_174500/
    ├── assets.db
    ├── arp_cat.db
    └── (directory markers)
```

Skip with `--skip-safety-backup` if you're confident.

### Important Notes

- **Stop Flask app before restoring** - Database must not be in use
- Restore is **destructive** - all current data will be replaced
- Safety backups protect against mistakes
- Checksum validation ensures data integrity

## Reset Utility

### Basic Usage

```bash
# Full reset with confirmation
python reset.py

# Force reset without confirmation (DANGEROUS!)
python reset.py --force

# Reset but preserve network maps
python reset.py --preserve-maps

# Reset without reinitializing databases
python reset.py --skip-reinit
```

### What Reset Does

1. Creates safety backup (unless `--skip-safety-backup`)
2. Removes all databases
3. Clears artifact directories
4. Reinitializes fresh database schema (unless `--skip-reinit`)
5. Verifies empty state

### Safety Features

- Requires typing "RESET" to confirm (unless `--force`)
- Creates safety backup before proceeding
- Checks for running Flask application
- Preserves backups directory by default

### Use Cases

- **Testing** - Reset to clean state between tests
- **Development** - Clear test data before production deployment
- **Recovery** - Start fresh after data corruption
- **Migration** - Clean slate before importing new data

## Complete Workflow Examples

### 1. Fresh Install Restore

Starting from fresh GitHub clone:

```bash
# Clone repository
git clone https://github.com/scottpeterman/anguisnms
cd anguisnms

# Setup Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Restore from backup
python restore.py --archive /path/to/anguis_backup.tar.gz --force

# Start application
cd app
python run.py
```

### 2. Testing Workflow

```bash
# Create baseline backup of production data
python backup.py --output ./test_fixtures

# Run tests...
python -m pytest

# Reset to clean state
python reset.py --force

# Restore production data
python restore.py --archive ./test_fixtures/anguis_backup_*.tar.gz --force
```

### 3. Upgrade Migration

```bash
# Before upgrade: backup current state
python backup.py --output ./pre_upgrade_backup

# Perform upgrade (git pull, etc.)
git pull origin main
pip install -r requirements.txt --upgrade

# If upgrade fails: restore previous state
python restore.py --archive ./pre_upgrade_backup/anguis_backup_*.tar.gz --force
```

### 4. Data Refresh Workflow

```bash
# Backup current production data (metadata only for speed)
python backup.py --output ./backups --no-captures

# Reset to empty state
python reset.py --force

# Run discovery and capture from pcng directory
cd pcng
python sc_run3.py --username admin --password secret --workers 10
python sc_enhance_all_maps.py --workers 10
python batch_spn_concurrent.py sessions.yaml --fingerprint-only
python batch_spn_concurrent.py sessions.yaml --fingerprinted-only
cd ..

# Load into database
python db_load_fingerprints.py --fingerprints-dir pcng/fingerprints
python db_load_captures.py --captures-dir pcng/capture
```

## Advanced Options

### Selective Backup Strategies

```bash
# Daily metadata backup (fast, small)
python backup.py --output ./daily --no-captures

# Weekly full backup (complete, large)
python backup.py --output ./weekly

# Monthly archive with logs
python backup.py --output ./monthly --include-logs
```

### Custom Project Locations

```bash
# Backup from custom location
python backup.py --project-root /opt/anguis --output /backups

# Restore to custom location
python restore.py --project-root /opt/anguis --archive backup.tar.gz
```

## Backup Retention Strategy

Recommended approach:

```bash
backups/
├── daily/          # Last 7 days, metadata-only
├── weekly/         # Last 4 weeks, full backup
├── monthly/        # Last 12 months, full backup with logs
└── test_fixtures/  # Known-good baselines
```

Example cron jobs:

```cron
# Daily metadata backup at 2 AM
0 2 * * * cd /path/to/anguis && python backup.py --output ./backups/daily --no-captures

# Weekly full backup on Sunday at 3 AM
0 3 * * 0 cd /path/to/anguis && python backup.py --output ./backups/weekly

# Monthly full backup on 1st at 4 AM
0 4 1 * * cd /path/to/anguis && python backup.py --output ./backups/monthly --include-logs
```

## Troubleshooting

### Database Locked Error

```
✗ Database is in use. Stop the Flask application before restoring.
```

**Solution:** Stop the Flask app first:
```bash
# Find Flask process
ps aux | grep "python run.py"

# Kill process
kill <PID>

# Or use pkill
pkill -f "python run.py"
```

### Checksum Mismatch

```
✗ Checksum mismatch: assets.db
```

**Solution:** Archive may be corrupted. Use a different backup or re-create from source.

### Restore Verification Warnings

```
⚠ Record count mismatches in assets.db:
  - devices: expected 358, got 355
```

**Common causes:**
- Backup created while data was being modified
- Partial backup/restore
- Database triggers not firing correctly

**Solution:** If counts are close, likely safe to proceed. For exact match, restore from a backup created with Flask app stopped.

### Reset Safety

If reset fails partway through:

1. Check `safety_backups/` for pre-reset backup
2. Restore from safety backup: `python restore.py --archive safety_backups/pre_reset_*/`
3. Or manually run `python db_init.py` and `python arp_cat_init_schema.py`

## Schema Versioning

Current schema version: **1.0.0**

Future versions will include migration support. For now:
- Backups from same schema version restore cleanly
- Cross-version restores may require manual migration
- Schema version stored in manifest for compatibility checking

## Performance Notes

Real-world timings for 357-device environment (based on actual backup run):

**Backup performance:**
- **Metadata-only (--no-captures):** ~5-10 seconds, ~15-20 MB compressed
- **Full backup:** ~15-30 seconds, ~50-80 MB compressed
  - 10,229 capture files (189 MB)
  - 443 fingerprint files (3 MB)
  - 262 map files (130 MB)
  - Databases (13 MB)
  - Compression ratio: ~17% (58 MB from 335 MB raw data)

**Restore performance:**
- **Extract and validate:** ~5-10 seconds
- **Full restore:** ~15-25 seconds
- **Verification:** ~2-5 seconds

**Reset performance:**
- **Complete reset:** ~2-5 seconds

**Scalability:**
Backup time and size scale primarily with:
- Number of devices (more configs, fingerprints)
- Capture types enabled (28 types available)
- Network map complexity
- Change tracking history

For larger deployments (500+ devices), expect proportionally larger archives and longer backup times.

## Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: Anguis Testing
on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Initialize environment
        run: python reset.py --force
      
      - name: Run tests
        run: python -m pytest
      
      - name: Create backup
        if: success()
        run: python backup.py --output ./artifacts
      
      - name: Upload backup
        uses: actions/upload-artifact@v2
        with:
          name: test-backup
          path: ./artifacts/*.tar.gz
```

## Security Considerations

- **Backups contain sensitive data** - Store securely
- **Credentials** - Not included in backups (stored in config.yaml)
- **Encryption** - Consider encrypting archives for offsite storage
- **Access control** - Restrict backup directory permissions

Example secure storage:

```bash
# Encrypt backup before offsite storage
gpg --symmetric --cipher-algo AES256 anguis_backup_*.tar.gz

# Decrypt when needed
gpg --decrypt anguis_backup_*.tar.gz.gpg > anguis_backup_*.tar.gz
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/scottpeterman/anguisnms/issues
- Documentation: See other README files in repository

## License

GNU General Public License v3.0 - Same as Anguis NMS