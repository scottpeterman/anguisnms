# Network Asset Management & Discovery Pipeline

A comprehensive Python-based network automation platform for device discovery, configuration capture, topology visualization, and asset inventory management with a professional web interface built on Flask and Material Design 3.

## Overview

This platform provides end-to-end network device management combining automated discovery pipelines, configuration backup systems, topology visualization, and a production-ready web interface for asset tracking and operational data access.

### Key Capabilities

**Automated Discovery Pipeline**
- Network topology discovery via CDP/LLDP using Secure Cartography
- TextFSM-based device fingerprinting with intelligent template matching
- Multi-vendor support (Cisco, Arista, Juniper, HPE, Fortinet, Palo Alto, F5)
- Hardware component extraction with serial number tracking
- Stack member detection and inventory
- Parallel processing for large-scale networks (2000+ devices)

**Configuration Capture & Management**
- 31 capture types (configs, inventory, routing tables, neighbor discovery, etc.)
- Automated capture scheduling and execution via batch processing
- Current/archive retention with 30-day historical data
- File-based storage with database indexing
- Success rate tracking and gap analysis

**Network Topology Visualization**
- Multi-format map generation (SVG, GraphML, DrawIO, JSON)
- Vendor-specific icon integration for professional diagrams
- Interactive web viewer with zoom, pan, fullscreen
- Automated thumbnail generation and caching
- Site-based organization with hierarchical browsing
- Separate views for engineering detail vs. executive presentation

**Web Interface (Flask + Material Design 3)**
- **Full CRUD Operations**: Create, Read, Update, Delete devices with validation
- **Integrated Content Viewers**: Instant access to captures, inventory, and fingerprint data in modal viewers
- **Advanced Filtering**: Search across devices by name, IP, vendor, site, role with pagination
- **Coverage Analysis**: Pipeline gap analysis and success rate tracking across vendors
- **Interactive Maps**: Topology visualization with multi-format support and download
- **Professional UI**: Three themes (Light, Dark, Cyber) with consistent Material Design 3 components
- **Mobile Responsive**: Optimized layouts for all screen sizes

**Database Architecture**
- 11 normalized tables with proper foreign key relationships
- Automated triggers for data consistency (have_sn, is_stack, stack_count)
- Optimized views for common queries (v_device_status, v_capture_coverage, v_site_inventory)
- Strategic indexing for performance at scale
- Current/archive pattern for temporal data management

## Architecture

```
Discovery Pipeline          Database Layer          Web Interface
─────────────────          ──────────────          ─────────────
Topology JSON               SQLite Database         Flask App
     ↓                            ↓                      ↓
map_to_session.py          11 Core Tables          Dashboard
     ↓                            ↓                      ↓
sessions.yaml              3 Optimized Views       Device CRUD
     ↓                            ↓                      ↓
device_fingerprint.py      Automated Triggers      Content Viewers
     ↓                            ↓                      ↓
Fingerprint JSONs          API Endpoints           Coverage Analysis
     ↓                            ↓                      ↓
batch_capture.py           Database Loaders        Network Maps
     ↓                            ↓                      ↓
Capture Files              ──────────────          ─────────────
```

## Quick Start

### Prerequisites
```bash
# Core requirements
Python 3.8+
pip install flask pyyaml textfsm netmiko networkx

# For network maps
pip install pillow cairosvg PyQt6 PyQt6-WebEngine

# For discovery
pip install secure_cartography
```

### Database Setup
```bash
# Create database with schema
sqlite3 assets.db < schema.sql  # See README.DB.md for schema

# Load sample data
python db_load_fingerprints.py --fingerprints-dir fingerprints --db-path assets.db
python db_load_captures.py --captures-dir capture --db-path assets.db
```

### Launch Web Interface
```bash
cd app
python run.py

# Access at http://localhost:5000
# Default credentials: admin / admin
```

## Core Features

### 1. Device Management (Full CRUD)

**Create Devices**
- Form-based device creation with validation
- Automatic name normalization for database uniqueness
- Dropdown selection for sites, vendors, device types, roles
- IP address format validation with octet range checking
- Inline help text and field descriptions

**View & Search**
- List view with advanced filtering (name, IP, vendor, site, role, stack status)
- Configurable pagination (10-100 devices per page)
- URL parameter persistence for filter state
- Detailed device pages with comprehensive information cards:
  - Basic info (name, site, role, management IP)
  - Hardware details (vendor, model, OS, device type, drivers)
  - Status & activity (capture counts, last fingerprint, timestamps)
- Tabbed interface showing serials, stack members, components, captures, fingerprints
- Real-time statistics and status indicators

**Update Devices**
- Pre-populated forms with current values
- Duplicate name checking (excluding current device)
- Full validation matching create workflow
- Success/error feedback with navigation

**Delete Devices**
- Confirmation modal with impact assessment
- Lists all affected records (captures, fingerprints, serials, components)
- Warning system showing data to be deleted
- Cascade deletion of all related data

### 2. Integrated Content Viewers

**Capture Viewer**
- Full-text display of any capture file (31 supported types)
- Modal-based interface with professional toolbar
- Copy to clipboard functionality
- Download as text file
- File metadata display (lines, size, timestamp)
- Handles large files with proper encoding

**Inventory Viewer**
- Formatted component reports from database
- Position, serial, and confidence data for each component
- Component counts and categorization by type
- Extraction metadata showing source and reliability

**Fingerprint Viewer**
- Syntax-highlighted JSON display with color coding:
  - Keys in primary color
  - Strings in tertiary color
  - Numbers in success color
  - Booleans in warning color
  - Nulls in error color
- Top-level key counts
- Template matching information
- Copy and download functionality

**Viewer Features**
- Professional toolbar with copy/download buttons
- Loading states during file retrieval
- Error handling with user-friendly messages
- Keyboard shortcuts (ESC to close)
- Background click to dismiss
- Mobile-responsive layout
- Proper UTF-8 handling for all content types

### 3. Network Discovery Pipeline

**Topology Discovery**
```bash
# Discover all sites in parallel
python sc_run3.py --username admin --password secret --workers 10 --output-dir ./maps

# Filter specific sites
python sc_run3.py --username admin --password secret --filter "datacenter,hq"
```

**Device Fingerprinting**
```bash
# Single device
python device_fingerprint.py --host 192.168.1.1 --fingerprint-output device.json

# Batch processing with concurrent execution
python batch_spn_concurrent.py sessions.yaml --fingerprint-only --max-processes 18
```

**What Gets Extracted:**
- Device hostname from prompt detection
- Hardware model and serial numbers
- Software version with intelligent field prioritization
- Stack member details with positions
- Hardware components with confidence scores
- Management IP addresses
- Device role auto-detection
- Vendor and device type mapping

### 4. Configuration Capture System

**Supported Capture Types (31 total):**
```
arp, authentication, authorization, bgp-neighbor, bgp-summary, bgp-table,
bgp-table-detail, cdp, cdp-detail, configs, console, eigrp-neighbor,
int-status, interface-status, inventory, ip_ssh, lldp, lldp-detail, mac,
ntp_status, ospf-neighbor, port-channel, routes, snmp_server, syslog,
tacacs, version
```

**Capture Workflow:**
```bash
# Single device capture
python spn.py --host 192.168.1.1 -c "show running-config" -o configs

# Batch capture across site with concurrent execution
python batch_spn_concurrent.py sessions.yaml \
    --vendor cisco \
    -c "show running-config,show version" \
    -o configs \
    --max-processes 10

# Fingerprint-aware execution (only on fingerprinted devices)
python batch_spn_concurrent.py sessions.yaml \
    --fingerprinted-only \
    -c "show interfaces status" \
    -o interface-status \
    --max-processes 8
```

### 5. Coverage Analysis

**Gap Analysis Dashboard** (`/coverage/`)
- Identifies which devices lack specific capture types
- Vendor-specific success rates (e.g., CDP vs LLDP compatibility)
- Device-level scoring (perfect coverage, partial, zero coverage)
- Site-grouped organization with folder structure
- Visual indicators (green checkmarks, red X marks)
- Actionable insights for pipeline improvements
- Summary statistics: total devices, capture types, success rates

**Operational Value:**
- Prioritizes collection gaps across inventory
- Reveals vendor-specific command compatibility issues
- Provides data-driven pipeline optimization
- Enables quality assurance for discovery operations

### 6. Network Topology Visualization

**Interactive Map Viewer** (`/maps/`)
- Thumbnail-based index showing all network maps
- Professional viewer with zoom, pan, fullscreen controls
- Multi-format support:
  - **SVG**: Clean Mermaid rendering for web display (core devices only)
  - **GraphML**: yEd-compatible with full topology and vendor icons
  - **DrawIO**: Draw.io-compatible for collaborative editing
  - **JSON**: Raw topology data for programmatic access
- Automated thumbnail generation with PNG caching
- Download capabilities for all source formats
- Site-based hierarchical organization

**Map Enhancement Pipeline:**
```bash
# Batch enhance all discovered maps
python enhance_all_maps.py --svg-no-endpoints --workers 10

# Single site enhancement
python sc_enhance_map3.py maps/site1/site1.json --svg-no-endpoints --layout tree
```

## Project Structure

```
.
├── app/                          # Flask web application
│   ├── blueprints/              # Route handlers
│   │   ├── assets/              # Device CRUD + Content API
│   │   ├── dashboard/           # Statistics overview
│   │   ├── capture/             # Capture search
│   │   ├── coverage/            # Gap analysis
│   │   ├── maps/                # Topology visualization
│   │   └── auth/                # Authentication
│   ├── static/
│   │   ├── css/themes.css       # Material Design 3 (2000+ lines)
│   │   └── js/theme-toggle.js   # Theme switching logic
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html           # Base layout with navigation
│   │   ├── assets/             # Device CRUD templates
│   │   │   ├── devices.html    # List view with filters
│   │   │   ├── device_detail.html  # Detail with content viewers
│   │   │   └── device_form.html    # Create/edit forms
│   │   ├── dashboard/          # Dashboard views
│   │   ├── capture/            # Search interface
│   │   ├── coverage/           # Gap analysis UI
│   │   └── maps/               # Map viewers
│   ├── utils/
│   │   └── database.py         # Database connection helper
│   └── run.py                  # Application entry point
│
├── Anguis/                        # Discovery pipeline tools
│   ├── device_fingerprint.py   # Enhanced TextFSM fingerprinting
│   ├── tfsm_fire.py           # Template engine with scoring
│   ├── spn.py                 # SSH execution engine
│   ├── ssh_client.py          # Robust SSH client
│   ├── batch_spn_concurrent.py # Multi-process batch execution
│   ├── run_jobs_concurrent_batch.py # Job orchestration
│   ├── map_to_session.py      # Topology to inventory converter
│   ├── sc_run3.py             # Parallel discovery wrapper
│   ├── sc_enhance_map3.py     # Single-site map enhancer
│   ├── enhance_all_maps.py    # Batch map enhancement
│   ├── gap_report.py          # HTML gap analysis
│   ├── search.py              # Advanced search algorithms
│   ├── capture/               # Capture file storage (31 types)
│   ├── fingerprints/          # Fingerprint JSON files
│   ├── maps/                  # Network topology files
│   └── sessions.yaml          # Device inventory
│
├── db_load_fingerprints.py    # Load fingerprints to database
├── db_load_captures.py        # Load captures to database
├── assets.db                  # SQLite database
│
└── Documentation
    ├── README.md              # This file
    ├── README.DB.md           # Database schema details
    ├── README_Network_Mgmt_Flask.md  # Frontend implementation
    ├── README_Pipeline.md     # Discovery pipeline guide
    ├── README_Fingerprinting.md  # TextFSM fingerprinting
    ├── README_Map_pipeline.md # Topology visualization
    ├── README_DB_Loaders.md   # Database loading utilities
    └── README_Batches.md      # Batch execution guide
```

## Web Interface Features

### Material Design 3 Theme System
- **Three themes**: Light (burgundy/cream), Dark (gray/burgundy), Cyber (matrix teal/green)
- **Theme persistence**: localStorage with instant switching via dropdown
- **Component library**: 40+ reusable MD3 components with `md-` prefix
- **Responsive design**: Mobile-first with breakpoints at 768px and 1024px
- **Consistent spacing**: 4px-32px system applied throughout
- **Professional modals**: Backdrop, animations, keyboard shortcuts

### Navigation Structure
```
Dashboard           - Real-time statistics and vendor/site summaries
└─ Device Management
   ├─ Devices       - Full CRUD with integrated content viewers ✅
   ├─ Stacks        - Stack management interface (planned)
   ├─ Components    - Component inventory browser (planned)
   ├─ Sites         - Site management (planned)
   └─ Vendors       - Vendor administration (planned)

Search & Analysis
├─ Device Search    - Advanced filtering ✅
└─ Capture Search   - Full-text search across captures ✅

Discovery
├─ Fingerprints     - Template management interface (planned)
├─ Captures         - Capture scheduling system (planned)
└─ Coverage         - Gap analysis and success rates ✅

Network Maps
├─ All Maps         - Interactive topology visualization ✅
└─ Live Status      - Real-time monitoring overlays (planned)

Tools
├─ SSH Terminal     - Web-based device access (planned)
└─ Export           - Data export and reporting (planned)
```

### Current Implementation Status
**Fully Operational (6 modules):**
1. Device Management - Full CRUD with content viewers
2. Dashboard - Statistics and overview
3. Capture Search - Full-text search
4. Coverage Analysis - Gap analysis and vendor compatibility
5. Network Maps - Interactive topology visualization
6. Authentication - Basic session management

**Feature Completeness:** ~30% implemented, ~70% planned

## API Endpoints

### Device Management
```
GET    /assets/devices                    # List with filtering/pagination
GET    /assets/devices/<id>                # Device detail page
GET    /assets/devices/create              # Create form
POST   /assets/devices/create              # Create device
GET    /assets/devices/<id>/edit           # Edit form
POST   /assets/devices/<id>/edit           # Update device
POST   /assets/devices/<id>/delete         # Delete device (with confirmation)
```

### Content Serving
```
GET    /assets/api/devices/<id>/capture/<type>      # Get capture content (text)
GET    /assets/api/devices/<id>/inventory           # Get formatted inventory
GET    /assets/api/devices/<id>/fingerprint/<ts>    # Get fingerprint JSON
```

### Statistics & Analytics
```
GET    /assets/api/devices/stats          # Vendor/site statistics
GET    /assets/api/devices/<id>/captures  # Capture history
GET    /coverage/api/stats                # Coverage statistics
GET    /maps/api/maps                     # Map metadata
```

## Database Schema

### Core Tables
- `devices` - Primary inventory (name, model, IP, vendor_id, device_type_id, role_id)
- `device_serials` - Serial tracking for stacked devices
- `stack_members` - Stack member details with positions
- `components` - Hardware components with extraction confidence
- `device_captures_current` - Latest captures (one per device/type)
- `device_captures_archive` - Historical data (30-day retention)
- `fingerprint_extractions` - Fingerprinting audit trail with template scores

### Reference Tables
- `vendors` - Manufacturer information
- `device_types` - Communication profiles (netmiko/napalm drivers)
- `device_roles` - Device classification with auto-detection patterns
- `sites` - Geographic/organizational sites

### Optimized Views
- `v_device_status` - Complete device info with automation drivers
- `v_capture_coverage` - Coverage analysis by capture type
- `v_site_inventory` - Device summary by site
- `v_stack_summary` - Switch stack configuration details (optional)

See `README.DB.md` for complete schema documentation.

## Configuration

### File Locations
- **Database**: `assets.db` (root directory)
- **Captures**: `Anguis/capture/` organized by type
- **Fingerprints**: `Anguis/fingerprints/` as JSON files
- **Maps**: `Anguis/maps/` organized by site
- **Sessions**: `Anguis/sessions.yaml` device inventory

### Environment Variables
```bash
# Credentials for batch operations
export CRED_1_USER="admin"
export CRED_1_PASS="password"
export CRED_2_USER="netadmin"
export CRED_2_PASS="netpass"
```

### Web Application
```python
# app/utils/database.py
DATABASE = 'assets.db'  # Relative to app directory

# app/run.py
app.run(host='0.0.0.0', port=5000, debug=False)
```

## Typical Workflows

### Daily Discovery & Update Cycle
```bash
# 1. Discover network topology (parallel, ~60-90 min for 300 sites)
python sc_run3.py --username admin --password secret --workers 10

# 2. Fingerprint devices (parallel, ~2-4 hours for 2000 devices)
python batch_spn_concurrent.py sessions.yaml \
    --fingerprint-only \
    --max-processes 18 \
    --fingerprint-base ./fingerprints

# 3. Capture configurations (parallel, ~2-4 hours)
python batch_spn_concurrent.py sessions.yaml \
    --fingerprinted-only \
    -c "show running-config,show version,show inventory" \
    -o configs \
    --max-processes 10

# 4. Load data into database (~5-10 minutes)
python db_load_fingerprints.py --fingerprints-dir fingerprints --db-path assets.db
python db_load_captures.py --captures-dir capture --db-path assets.db

# 5. Enhance network maps (parallel, ~2-3 hours)
python enhance_all_maps.py --svg-no-endpoints --workers 10

# 6. Generate reports
python gap_report.py --output reports/gap_analysis.html
```

### Web Interface Usage
```bash
# 1. Start web application
cd app && python run.py

# 2. Access dashboard
http://localhost:5000/dashboard/

# 3. Manage devices
http://localhost:5000/assets/devices
- Create new devices via form
- Edit existing devices
- View capture files in modal viewer
- Access fingerprint JSON data
- Delete devices with confirmation

# 4. Analyze coverage
http://localhost:5000/coverage/

# 5. View topology maps
http://localhost:5000/maps/
```

## Performance Characteristics

### Scalability
- **Devices**: Tested with 2000+ devices
- **Sites**: Tested with 400+ sites
- **Capture Types**: 31 different operational data types
- **Concurrent Processing**: Up to 20 parallel processes
- **Database Size**: ~6.5 GB with 30-day archive retention

### Processing Times
- **Fingerprinting**: 2-7 seconds per device (varies by vendor)
- **Configuration Capture**: 15-30 seconds per device
- **Batch Processing**: ~4 hours for 2000 devices (8-10 processes)
- **Gap Analysis**: ~5 minutes for complete inventory
- **Map Enhancement**: ~20-35 seconds per site with SVG

### Web Interface Performance
- **Page Load**: <1 second for device lists (with pagination)
- **Content Viewer**: 1-3 seconds for capture file retrieval
- **Search**: Sub-second for filtered queries with indexes
- **Theme Switching**: Instant via CSS custom properties

## Key Improvements in Current Release

### Device Management Enhancements
- Full CRUD operations with comprehensive validation
- Integrated content viewers for instant data access
- Professional modal system with copy/download
- Confirmation dialogs with impact assessment
- Form validation for IP addresses and names

### Content Access Revolution
- Single-click viewing of any capture file
- Syntax-highlighted JSON for fingerprints
- Copy to clipboard with visual feedback
- Download functionality for all content types
- File metadata display (size, lines, keys)
- Proper UTF-8 handling and error messages

### User Experience
- Material Design 3 consistency across all pages
- Loading states during async operations
- Error handling with actionable messages
- Mobile responsive design throughout
- Keyboard shortcuts for modal operations
- Three theme options (Light, Dark, Cyber)

## Use Cases

### Network Operations
- **Device Inventory**: Complete hardware tracking with automation metadata
- **Configuration Backup**: Automated capture with current/archive pattern
- **Change Management**: Historical archive for compliance and rollback
- **Gap Analysis**: Identify missing data and optimize collection

### Network Planning
- **Topology Visualization**: Interactive maps for planning and documentation
- **Hardware Tracking**: Component-level inventory for lifecycle management
- **Stack Management**: Track switch stacks with member details
- **Coverage Reporting**: Vendor compatibility and success rate analysis

### Troubleshooting
- **Quick Access**: Instant viewing of configs and operational data via web interface
- **Search Capabilities**: Full-text search across all captures
- **Historical Data**: Access to archived configurations for comparison
- **Component Details**: Hardware inventory for RMA and support cases

## Documentation

- **README.md** (this file) - Platform overview and quick start
- **README.DB.md** - Complete database schema with SQL
- **README_Network_Mgmt_Flask.md** - Frontend implementation details and API
- **README_Pipeline.md** - Discovery pipeline architecture and workflows
- **README_Fingerprinting.md** - TextFSM fingerprinting with template matching
- **README_Map_pipeline.md** - Topology discovery and visualization
- **README_DB_Loaders.md** - Database loading utilities and daily workflows
- **README_Batches.md** - Batch execution guide for concurrent processing

## Security Considerations

- **Credentials**: Never hardcode credentials - use environment variables
- **Authentication**: Current implementation is dev-grade (admin/admin)
- **Network Access**: Ensure SSH connections use proper security
- **Data Sensitivity**: Device information may be confidential
- **File Permissions**: Restrict access to database and capture files
- **Debug Output**: Contains detailed device info - secure logs appropriately

## Support & Contributing

Key areas for contribution:
- Additional vendor support (Juniper, Palo Alto templates)
- Enhanced TextFSM templates for fingerprinting
- Real-time monitoring features in web interface
- API integrations with ITSM systems
- Performance optimization for large-scale deployments
- Mobile app for field technicians

## License

[Your License Here]

---

**Production Note**: This platform is designed for internal network management. Implement proper authentication, access controls, and security hardening before production deployment. Current authentication system (admin/admin) is development-grade only.

## Overview

This platform provides end-to-end network device management with automated discovery, configuration backup, and a professional web interface for asset tracking and operational data access.

### Key Features

**Device Discovery & Fingerprinting**
- Automated device identification using TextFSM templates
- Multi-vendor support (Cisco, Arista, Juniper, HPE, Fortinet, Palo Alto, F5)
- Hardware component extraction with serial number tracking
- Stack member detection and inventory

**Configuration Capture System**
- 31 capture types (configs, inventory, routing tables, neighbor discovery, etc.)
- Automated capture scheduling and execution
- Current/archive retention with 30-day historical data
- File-based storage with database indexing

**Web Interface (Flask)**
- **Full CRUD Operations**: Create, Read, Update, Delete devices with validation
- **Integrated Content Viewers**: Instant access to captures, inventory, and fingerprint data
- **Advanced Filtering**: Search across devices by name, IP, vendor, site, role
- **Coverage Analysis**: Pipeline gap analysis and success rate tracking
- **Network Maps**: Interactive topology visualization with multi-format support
- **Material Design 3**: Professional UI with Light, Dark, and Cyber themes

**Database Architecture**
- 11 normalized tables with proper foreign key relationships
- Automated triggers for data consistency
- Optimized views for common queries
- Strategic indexing for performance

## Quick Start

### Prerequisites
```bash
# Python 3.8+
pip install flask sqlite3 pyyaml textfsm netmiko

# Optional for network maps
pip install pillow cairosvg
```

### Database Setup
```bash
# Create database with schema
sqlite3 assets.db < README.DB.md  # Use SQL from database documentation

# Or use the included schema file
python db_setup.py
```

### Launch Web Interface
```bash
cd app
python run.py

# Access at http://localhost:5000
# Default credentials: admin / admin
```

## Core Capabilities

### 1. Device Management (Full CRUD)

**Create Devices**
- Form-based device creation with validation
- Automatic name normalization for database uniqueness
- Dropdown selection for sites, vendors, device types, roles
- IP address format validation
- Inline help text and field descriptions

**View & Search**
- List view with advanced filtering (name, IP, vendor, site, role, stack status)
- Configurable pagination (10-100 devices per page)
- Detailed device pages with comprehensive information cards
- Tabbed interface showing serials, stack members, components, captures, fingerprints
- Real-time statistics and status indicators

**Update Devices**
- Pre-populated forms with current values
- Duplicate name checking (excluding current device)
- Full validation matching create workflow
- Success/error feedback with navigation

**Delete Devices**
- Confirmation modal with impact assessment
- Lists all affected records (captures, fingerprints, serials, components)
- Cascade deletion of all related data
- Warning system for devices with operational data

### 2. Integrated Content Viewers

**Capture Viewer**
- Full-text display of any capture file
- Supports all 31 capture types (config, inventory, routes, neighbors, etc.)
- Copy to clipboard functionality
- Download as text file
- File metadata display (lines, size)

**Inventory Viewer**
- Formatted component reports with position, serial, and confidence data
- Automatically generated from database components
- Component counts and categorization

**Fingerprint Viewer**
- Syntax-highlighted JSON display
- Color-coded keys, strings, numbers, booleans, nulls
- Top-level key counts
- Copy and download functionality

**Viewer Features**
- Modal-based design with professional toolbar
- Loading states during file retrieval
- Error handling with user-friendly messages
- Keyboard shortcuts (ESC to close)
- Background click to dismiss
- Mobile-responsive layout

### 3. Device Discovery Pipeline

**Fingerprinting Process**
```bash
# Run device fingerprinting
python Anguis/device_fingerprint.py --device-name nyc-core-01

# Batch processing
python Anguis/batch_fingerprint.py --site NYC
```

**What Gets Extracted:**
- Device name, model, OS version
- Hardware components with serial numbers
- Stack member details and positions
- Management IP addresses
- Device role auto-detection

### 4. Configuration Capture

**Capture Types Supported:**
```
arp, authentication, authorization, bgp-neighbor, bgp-summary, bgp-table,
bgp-table-detail, cdp, cdp-detail, configs, console, eigrp-neighbor,
int-status, interface-status, inventory, ip_ssh, lldp, lldp-detail, mac,
ntp_status, ospf-neighbor, port-channel, routes, snmp_server, syslog,
tacacs, version
```

**Capture Workflow:**
```bash
# Run capture for single device
python Anguis/capture_device.py --device nyc-core-01 --type config

# Batch capture across site
python Anguis/batch_capture.py --site NYC --types config,inventory,version
```

### 5. Coverage Analysis

**Gap Analysis Dashboard**
- Shows which devices lack specific capture types
- Vendor-specific success rates (e.g., CDP vs LLDP compatibility)
- Device-level scoring (perfect coverage, partial, zero coverage)
- Site-grouped organization
- Actionable insights for pipeline improvements

### 6. Network Maps

**Topology Visualization**
- Thumbnail-based index showing all network maps
- Interactive viewer with zoom, pan, fullscreen
- Multi-format support (SVG, JSON, GraphML, DrawIO)
- Automated thumbnail generation
- Download capabilities for source files
- Site-based organization

## Project Structure

```
.
├── app/                          # Flask web application
│   ├── blueprints/              # Route handlers
│   │   ├── assets/              # Device management CRUD + API
│   │   ├── dashboard/           # Statistics overview
│   │   ├── capture/             # Capture search
│   │   ├── coverage/            # Gap analysis
│   │   ├── maps/                # Topology visualization
│   │   └── auth/                # Authentication
│   ├── static/
│   │   ├── css/themes.css       # Material Design 3 styles
│   │   └── js/theme-toggle.js   # Theme switching
│   ├── templates/               # Jinja2 templates
│   │   ├── base.html           # Base layout with navigation
│   │   ├── assets/             # Device CRUD templates
│   │   ├── dashboard/          # Dashboard views
│   │   ├── capture/            # Search interface
│   │   ├── coverage/           # Gap analysis
│   │   └── maps/               # Map viewers
│   ├── utils/
│   │   └── database.py         # Database connection helper
│   └── run.py                  # Application entry point
├── Anguis/                        # Discovery pipeline tools
│   ├── device_fingerprint.py   # Device identification
│   ├── capture_device.py       # Configuration capture
│   ├── batch_*.py              # Batch processing scripts
│   ├── capture/                # Capture file storage
│   ├── fingerprints/           # Fingerprint JSON files
│   └── maps/                   # Network topology files
├── assets.db                   # SQLite database
├── README.DB.md               # Database schema documentation
└── README_Network_Mgmt_Flask.md # Frontend implementation guide
```

## Web Interface Features

### Material Design 3 Theme System
- **Three themes**: Light (burgundy/cream), Dark (gray/burgundy), Cyber (matrix teal/green)
- **Theme persistence**: localStorage with instant switching
- **Component library**: 40+ reusable MD3 components
- **Responsive design**: Mobile-first with breakpoints

### Navigation Structure
```
Dashboard           - Real-time statistics
└─ Device Management
   ├─ Devices       - Full CRUD with content viewers ✅
   ├─ Stacks        - Stack management (planned)
   ├─ Components    - Component inventory (planned)
   ├─ Sites         - Site management (planned)
   └─ Vendors       - Vendor administration (planned)

Search & Analysis
├─ Device Search    - Advanced filtering ✅
└─ Capture Search   - Full-text search ✅

Discovery
├─ Fingerprints     - Template management (planned)
├─ Captures         - Capture scheduling (planned)
└─ Coverage         - Gap analysis ✅

Network Maps
├─ All Maps         - Topology visualization ✅
└─ Live Status      - Real-time monitoring (planned)

Tools
├─ SSH Terminal     - Web-based device access (planned)
└─ Export           - Data export (planned)
```

## API Endpoints

### Device Management
```
GET    /assets/devices                    # List devices with filtering
GET    /assets/devices/<id>                # Device detail page
GET    /assets/devices/create              # Create form
POST   /assets/devices/create              # Create device
GET    /assets/devices/<id>/edit           # Edit form
POST   /assets/devices/<id>/edit           # Update device
POST   /assets/devices/<id>/delete         # Delete device
```

### Content Serving
```
GET    /assets/api/devices/<id>/capture/<type>      # Get capture content
GET    /assets/api/devices/<id>/inventory           # Get inventory report
GET    /assets/api/devices/<id>/fingerprint/<ts>    # Get fingerprint JSON
```

### Statistics
```
GET    /assets/api/devices/stats          # Vendor/site statistics
GET    /assets/api/devices/<id>/captures  # Capture history
```

## Database Schema Highlights

### Core Tables
- `devices` - Primary device inventory (11 columns + foreign keys)
- `device_serials` - Serial number tracking for stacked devices
- `stack_members` - Stack member details with positions
- `components` - Hardware components with extraction confidence
- `device_captures_current` - Latest captures (one per device/type)
- `device_captures_archive` - Historical data (30-day retention)
- `fingerprint_extractions` - Fingerprinting audit trail

### Reference Tables
- `vendors` - Manufacturer information
- `device_types` - Communication profiles (netmiko/napalm drivers)
- `device_roles` - Device classification with auto-detection patterns
- `sites` - Geographic/organizational sites

### Optimized Views
- `v_device_status` - Complete device info with automation drivers
- `v_capture_coverage` - Coverage analysis by capture type
- `v_site_inventory` - Device summary by site

## Configuration

### Database Location
Default: `assets.db` in project root. Configure in `app/utils/database.py`:
```python
DATABASE = 'assets.db'
```

### Capture File Storage
Default: `Anguis/capture/` directory. Organized by capture type:
```
Anguis/capture/
├── config/
├── inventory/
├── version/
└── ...
```

### Fingerprint Storage
Default: `Anguis/fingerprints/` directory. JSON files named by device:
```
Anguis/fingerprints/
├── nyc-core-01_2025-09-29T10:00:00.json
├── cal-hr02-swl-01_2025-09-29T10:05:00.json
└── ...
```

### Map Storage
Default: `Anguis/maps/` directory. Organized by site:
```
Anguis/maps/
├── NYC/
│   ├── datacenter.svg
│   └── distribution.svg
├── CAL/
│   └── site-topology.svg
└── thumbnails/
    ├── NYC/
    └── CAL/
```

## Development Status

**Production-Ready Features (6 modules):**
1. Device Management - Full CRUD with integrated content viewers
2. Dashboard - Statistics and overview
3. Capture Search - Full-text search across captures
4. Coverage Analysis - Gap analysis and vendor compatibility
5. Network Maps - Interactive topology visualization
6. Authentication - Basic session management

**In Development:**
- Site/Vendor/Role management interfaces
- Capture scheduling and automation
- Real-time monitoring overlays
- SSH terminal integration

**Feature Completeness:** ~30% implemented, 70% planned

See `README_Network_Mgmt_Flask.md` for detailed frontend implementation status.

## Key Improvements in Latest Release

### Device Management Enhancements
- **Full CRUD operations** with form validation and error handling
- **Integrated content viewers** for captures, inventory, and fingerprints
- **Professional modal system** with copy/download functionality
- **Confirmation dialogs** for destructive operations
- **Impact assessment** showing affected records before deletion

### Content Access
- **Instant viewing** of capture files without leaving device page
- **Syntax highlighting** for JSON fingerprint data
- **Copy to clipboard** with visual feedback
- **Download functionality** for all content types
- **File metadata** display (size, lines, keys)

### User Experience
- **Material Design 3** consistency across all pages
- **Loading states** during async operations
- **Error handling** with user-friendly messages
- **Mobile responsive** design throughout
- **Keyboard shortcuts** for modal operations

## Use Cases

### Network Operations
- **Device Inventory**: Track all network devices with complete hardware details
- **Configuration Backup**: Automated capture of configs and operational data
- **Change Management**: Historical capture archive for compliance
- **Gap Analysis**: Identify missing data and optimize collection pipeline

### Network Planning
- **Topology Visualization**: Interactive maps for planning and documentation
- **Hardware Tracking**: Component-level inventory for lifecycle management
- **Stack Management**: Track switch stacks with member details
- **Coverage Reporting**: Vendor compatibility and success rate analysis

### Troubleshooting
- **Quick Access**: Instant viewing of configs and operational data
- **Search Capabilities**: Full-text search across all captures
- **Historical Data**: Access to archived configurations
- **Component Details**: Hardware inventory for RMA and support

## Contributing

This is an active development project. Key areas for contribution:
- Additional device type support
- Enhanced TextFSM templates
- Real-time monitoring features
- API integrations
- Performance optimization

## License

[Your License Here]

## Documentation

- `README.DB.md` - Complete database schema documentation
- `README_Network_Mgmt_Flask.md` - Frontend implementation details
- `README_Pipeline.md` - Discovery pipeline documentation
- `README_Fingerprinting.md` - Device identification guide

## Support

For issues, questions, or feature requests, please [open an issue](link-to-issues).

---

**Note**: This platform is designed for internal network management. Ensure proper authentication and access controls before deploying in production environments.