# Anguis Network Management System

**Python-based network device discovery, inventory management, and configuration tracking system**

---

## ⚠️ Alpha Release

This is an early alpha release. While functional in production environments (managing 357 devices across 53 sites), expect rough edges and ongoing development. Released under GPLv3 to establish prior art before employment change.

**Current Status:**
- Core functionality complete and tested
- 11 operational modules working
- Documentation comprehensive but evolving
- Active development and refinement ongoing

---

## What This Does

Anguis automates network infrastructure management through integrated discovery, fingerprinting, and web-based asset tracking:

1. **Discovers networks** - CDP/LLDP topology mapping with parallel site processing
2. **Identifies devices** - TextFSM fingerprinting with 100+ vendor templates  
3. **Captures configurations** - 31 operational data types across multi-vendor environments
4. **Tracks inventory** - Hardware component extraction and serial number management
5. **Monitors changes** - Configuration diff monitoring with unified viewer
6. **Provides visibility** - 11 operational modules for real-time infrastructure visibility

**Tested Scale:**
- 357 devices across 53 sites
- 126 switch stacks managed
- 1,684 components tracked
- Multi-vendor: Cisco, Arista, HPE, F5, Juniper

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/scottpeterman/anguisnms
cd anguisnms

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Initialize databases
python db_init.py
python arp_cat_init_schema.py
```

### Basic Workflow

```bash
# 1. Discover network topology
cd pcng
python sc_run3.py --username admin --password secret --workers 10

# 2. Generate visual maps
python sc_enhance_all_maps.py --svg-no-endpoints --workers 10

# 3. Fingerprint devices
python batch_spn_concurrent.py sessions.yaml --fingerprint-only

# 4. Capture configurations  
python batch_spn_concurrent.py sessions.yaml --fingerprinted-only

# 5. Load into database
cd ..
python db_load_fingerprints.py --fingerprints-dir pcng/fingerprints
python db_load_captures.py --captures-dir pcng/capture

# 6. Launch web interface
cd app
python run.py
# Access at http://localhost:8086
```

---

## Key Features

### Network Discovery
- Parallel site discovery (295 sites in 45-60 minutes)
- CDP/LLDP topology mapping with site isolation
- SVG, GraphML, and DrawIO export formats
- Automatic vendor icon integration
- yEd-compatible hierarchical layouts

### Device Management
- Multi-vendor support (Cisco IOS/NX-OS, Arista EOS, HPE, Juniper)
- TextFSM-based fingerprinting with 100+ templates
- 31 operational capture types (configs, inventory, ARP, routing, VLANs, etc.)
- Parallel execution (8 concurrent processes)
- Success rates: 85%+ fingerprinting, high capture rates

### Component Inventory
- Automatic extraction from show inventory
- Tracks: Chassis, modules, PSUs, fans, transceivers
- Serial number coverage: 89.6%
- Multi-vendor templates (Cisco, Arista, HPE)
- 100% success on Cisco/Arista platforms

### Web Dashboard (11 Complete Modules)
- **Dashboard** - Network overview and real-time metrics
- **Devices** - Full CRUD operations with filtering and export
- **Components** - Hardware inventory browser (1,684 items)
- **OS Versions** - Compliance tracking (90.5% coverage)
- **Capture Search** - Full-text configuration search
- **Coverage Analysis** - Data collection gap identification
- **Changes** - Configuration diff monitoring
- **Network Maps** - Topology visualization
- **ARP Search** - MAC address lookup (7,658 entries)
- **SSH Terminal** - Web-based live device access
- **Bulk Operations** - Safe batch modifications
- **Notes** - Integrated documentation system

### Advanced Capabilities
- Multi-backend authentication (Windows/Linux/LDAP)
- WebSocket-based SSH sessions
- Preview-commit workflow for bulk changes
- Component-level inventory tracking
- Multi-vendor MAC normalization
- Full-text search with FTS5
- Rich text notes with image support
- CSV export across all modules

### Backup & Restore System

Complete lifecycle management utilities for disaster recovery and deployment:

**Features:**
- **Full backup** - Databases + all artifacts in single compressed archive
- **Metadata-only backup** - Fast snapshots excluding large capture files
- **Complete restore** - From GitHub clone to production in minutes
- **Environment reset** - Clean slate for testing or migration
- **Safety backups** - Automatic pre-restore/pre-reset snapshots
- **Integrity validation** - SHA256 checksums and record count verification

**Real-world performance** (357-device environment):
- Backup time: 15-30 seconds
- Archive size: ~58 MB (17% compression ratio)
- Restore time: 15-25 seconds
- 10,229 capture files + 443 fingerprints + 262 maps

**Usage:**
```bash
# Create full backup
python backup.py --output ./backups

# Metadata-only backup (faster, smaller)
python backup.py --output ./backups --no-captures

# Restore from backup
python restore.py --archive ./backups/anguis_backup_*.tar.gz

# Reset to clean state
python reset.py
```

**Deployment workflow:**
```bash
# Fresh clone to working system
git clone https://github.com/scottpeterman/anguisnms
cd anguisnms
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python db_init.py && python arp_cat_init_schema.py
python restore.py --archive /path/to/backup.tar.gz --force
cd app && python run.py
```

See [README_Maintenance.md](README_Maintenance.md) for complete documentation.

---

## Architecture

```
Network Devices → Discovery (CDP/LLDP)
                ↓
         Topology JSON
                ↓
    Maps (SVG/GraphML/DrawIO)
                ↓
   Device Fingerprinting (TextFSM)
                ↓
 Configuration Capture (31 types)
                ↓
      SQLite Database
                ↓
   Flask Web Dashboard
```

**Pipeline Components:**
- `sc_run3.py` - Parallel network discovery with site isolation
- `sc_enhance_all_maps.py` - Visual topology generation with vendor icons
- `batch_spn_concurrent.py` - Multi-process fingerprinting and capture
- `inventory_loader.py` - Component extraction from inventory captures
- `arp_cat_loader.py` - MAC address tracking with vendor normalization
- Flask app - Web-based management interface

---

## Performance

**Real-World Timings:**
- Discovery: 45-60 minutes (295 sites, 10 workers)
- Map Enhancement: 30-45 minutes (10 workers)
- Fingerprinting: 60-90 minutes (8 processes)
- Configuration Capture: 90-120 minutes (8 processes)
- Component Extraction: <3 seconds per device
- Dashboard Load: <500ms
- Export Generation: <2s for 357 devices

**Complete Cycle:** ~4 hours for full network refresh

**Coverage Rates:**
- Discovery: 95%+ topology mapping
- Fingerprinting: 85%+ device identification  
- OS Version Coverage: 90.5%
- Component Serial Numbers: 89.6%

---

## Documentation

### Core Guides
- **[Maps Pipeline](README_Map_pipeline.md)** - Discovery and topology generation
- **[Data Pipeline](README_Pipeline.md)** - Fingerprinting and configuration capture
- **[Web Dashboard](README_Network_Mgmt_Flask.md)** - Flask application and modules
- **[Component Inventory](README_Inventory_Components.md)** - Hardware tracking system
- **[Authentication](README_Auth.md)** - Multi-backend auth (Windows/Linux/LDAP)
- **[Backup & Restore](README_Maintenance.md)** - Lifecycle management utilities

### Additional Documentation
- **[Database Schema](README.DB.md)** - SQLite schema and design
- **[ARP Tracking](README_arp_cat.md)** - MAC address management
- **[Change Detection](README_Archive_change_detection.md)** - Configuration monitoring
- **[Notes System](README_Notes.md)** - Integrated documentation

---

## Project Evolution

**2024:** Initial proof of concept with CDP/LLDP discovery and dual SNMP/SSH support

**2024-2025:** [Secure Cartography](https://github.com/scottpeterman/secure_cartography) - Production-scale parallel discovery engine (295 sites in 45-60 minutes)

**2025:** Anguis - Integrated platform combining discovery, fingerprinting, component tracking, comprehensive web dashboard, and backup/restore utilities

---

## Requirements

**Core Dependencies:**
- Python 3.8+
- Core: paramiko, pyyaml, networkx, textfsm
- Web: flask, flask-socketio, python-socketio
- Optional: secure_cartography, Pillow

**Platform-Specific:**
- pywin32 (Windows authentication)
- python-pam (Linux authentication)  
- ldap3 (LDAP authentication)

See `requirements.txt` for complete dependencies.

---

## Configuration

**Database Initialization:**
```bash
python db_init.py                # Main assets database
python arp_cat_init_schema.py   # ARP tracking database
```

**Application Setup:**
- Create `config.yaml` from `config.yaml.example`
- Configure authentication backend (local/LDAP)
- Set credential management for discovery/capture
- See `README_Auth.md` for authentication setup

**First Run:**
```bash
cd app
python run.py
# Default credentials: admin / admin (local auth)
```

---

## Alpha Status & Expectations

This release establishes prior art before employment change. While functional in production environments, expect:

- Ongoing refinement of UI/UX
- Additional vendor template development
- Enhanced error handling and logging
- Performance optimization for large deployments

Core functionality is stable and tested. The platform successfully manages 357 devices across 53 sites with multi-vendor support.

---

## License

GNU General Public License v3.0

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See [LICENSE](LICENSE) for details.

---

## Related Projects

- [Secure Cartography](https://github.com/scottpeterman/secure_cartography) - Network discovery engine
- [Velociterm](https://github.com/scottpeterman/velociterm) - SSH terminal framework

---

*Alpha Release | October 2025 | scottpeterman*