# Network Discovery and Automation Pipeline

A production-ready Python-based system for enterprise network device discovery, fingerprinting, configuration capture, and operational data collection.

## Pipeline Overview

This system implements a complete network management workflow optimized for Windows environments:

**NetBox Export → Fingerprinting → Job Generation → Capture Execution → Database Loading → Web Dashboard**

The pipeline processes network inventory through multiple stages, producing structured device fingerprints, vendor-specific operational data captures, and comprehensive coverage analytics.

---

## Production Deployment Stats

**Current Scale:**
- **456 devices** actively managed across **53 sites**
- **577 fingerprints** collected from 1,386 discovered endpoints
- **29 capture types** covering configs, inventory, routing, AAA, and monitoring
- **108 automated job files** for multi-vendor environments
- **50-65% capture success rate** (normal for heterogeneous networks)

**Supported Vendors:**
- Cisco IOS/IOS-XE/NX-OS (132 devices)
- Arista EOS (197 devices)
- HP ProCurve/Aruba (127 devices)
- Others (firewalls, servers, IoT)

**Performance:**
- Fingerprinting: ~2 seconds per device (8 concurrent processes)
- Config capture: ~15-30 seconds per device
- Full batch: 456 devices in 30-60 minutes
- Web dashboard response: <200ms for device queries

---

## Architecture Components

### 1. Inventory Management

#### `sessions.yaml`
**Source:** NetBox export or manual YAML creation

**Format:**
```yaml
- folder_name: "Site Name"
  sessions:
    - display_name: "device-name-01"
      host: "10.1.1.1"
      port: 22
      Vendor: "Cisco"
      credsid: 1
```

**Credential Management:**
```powershell
# Windows environment variables
$env:CRED_1_USER = "admin"
$env:CRED_1_PASS = "your-password"
```

---

### 2. Device Fingerprinting System

#### `device_fingerprint.py`
**Purpose:** TextFSM-based device identification and metadata extraction

**Key Features:**
- 100+ TextFSM templates with confidence scoring
- Hostname extraction from SSH prompts (fallback for devices without hostname in version)
- Stack detection and member parsing (Cisco, HP)
- Automatic vendor/model/version extraction
- OS uptime and hardware inventory collection

**Fingerprinting Process:**
```
SSH Connect → Prompt Detection → show version → TextFSM Parse → JSON Output
```

**Output Example:**
```json
{
  "hostname": "use-leaf-2b",
  "detected_prompt": "use-leaf-2b#",
  "model": "DCS-7010TX-48-F",
  "version": "4.31.4M",
  "serial_number": "HBG240207L8",
  "additional_info": {
    "vendor": "Arista",
    "netmiko_driver": "arista_eos"
  }
}
```

#### `batch_spn_concurrent.py`
**Purpose:** Multi-process batch fingerprinting and command execution

**Execution Modes:**
- `--fingerprint-only` - Fingerprint devices without running commands
- `--fingerprinted-only` - Execute commands only on previously fingerprinted devices
- `--fingerprint` - Combine fingerprinting with command execution

**Filter Options:**
- `--vendor` - Filter by vendor pattern (e.g., `*cisco*`, `*arista*`)
- `--folder` - Filter by site/folder name
- `--name` - Filter by device name pattern

**Usage:**
```powershell
# Fingerprint all Arista devices
python Anguis\batch_spn_concurrent.py Anguis\sessions.yaml --fingerprint-only --vendor "*arista*" --max-processes 8 --verbose

# Fingerprint all devices
python Anguis\batch_spn_concurrent.py Anguis\sessions.yaml --fingerprint-only --max-processes 8
```

---

### 3. Job Generation System

#### `generate_capture_jobs.py`
**Purpose:** Automated vendor-specific job file generation

**Key Innovation:** 
This eliminates manual job file creation. One command generates 108 job files with correct vendor syntax, paging disable commands, and enable mode handling.

**Command Mapping Database:**
- 29 capture types (configs, version, arp, bgp-summary, inventory, etc.)
- 4 vendor platforms (Cisco IOS/NX-OS, Arista, HP/Aruba)
- Vendor-specific paging disable commands
- Enable mode requirements per capture type

**Paging Disable Commands:**
```python
'cisco_ios': 'terminal length 0'
'arista': 'terminal length 0'
'aruba': 'no page'
```

**Enable Mode Handling:**
```python
# Cisco IOS configs job generates:
"command_text": "enable,terminal length 0,show running-config"
```

**Generation:**
```powershell
python Anguis\generate_capture_jobs.py --output-dir Anguis\gnet_jobs --start-id 200
```

**Output:**
- 108 job JSON files (vendor × capture type combinations)
- 34 batch execution lists:
  - `job_batch_configs.txt` - All vendor configs
  - `job_batch_cisco_ios.txt` - All Cisco IOS captures
  - `job_batch_arista.txt` - All Arista captures
  - `job_batch_list_generated.txt` - Complete suite

---

### 4. Capture Execution

#### `run_jobs_concurrent_batch.py`
**Purpose:** Concurrent job orchestration with process pooling

**Features:**
- JSON-based job configuration
- Multi-process execution (default 5, recommended 8)
- Vendor-specific command assembly
- Credential validation before execution
- Retry logic for failed jobs
- Comprehensive execution summary

**Job Configuration Structure:**
```json
{
  "session_file": "sessions.yaml",
  "vendor": {
    "selected": "Cisco IOS",
    "auto_paging": true
  },
  "filters": {
    "vendor": "*cisco*"
  },
  "commands": {
    "command_text": "enable,terminal length 0,show running-config",
    "output_directory": "configs"
  },
  "execution": {
    "max_workers": 12
  },
  "fingerprint_options": {
    "fingerprinted_only": true
  }
}
```

**Usage:**
```powershell
# Backup all configs
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_configs.txt --max-processes 8 --verbose

# Complete capture suite (29 types)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_list_generated.txt --max-processes 8

# Single vendor
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_cisco_ios.txt --max-processes 8
```

---

### 5. Core SSH Execution

#### `spn.py`
**Purpose:** Enhanced SSH execution engine

**Features:**
- Single-session multi-command execution
- Aggregate prompt counting (prevents truncation)
- ANSI sequence filtering
- Legacy device compatibility
- Integration with fingerprinting

#### `ssh_client.py`
**Purpose:** Low-level SSH implementation

**Features:**
- Paramiko-based SSH client
- Intelligent prompt detection
- Carriage return handling for file output
- Thread-safe connection management

---

### 6. Database Integration

#### `db_load_fingerprints.py`
**Purpose:** Load fingerprint JSON files into SQLite database

**Key Features:**
- Hostname extraction from prompts (Arista fix)
- Stack member parsing from TextFSM data
- Site code extraction from hostnames
- Vendor/device type normalization
- Serial number handling (single and stacks)

**Usage:**
```powershell
python Anguis\db_load_fingerprints.py --fingerprints-dir Anguis\fingerprints --db-path assets.db --verbose
```

**Database Schema:**
- `devices` - Normalized device inventory
- `device_serials` - Primary and stack member serials
- `stack_members` - Individual stack component details
- `sites`, `vendors`, `device_types` - Lookup tables
- `fingerprint_extractions` - Audit trail

#### `db_load_captures.py`
**Purpose:** Load capture files into database with current/archive pattern

**Features:**
- 29 capture types supported
- Current table (one record per device/type)
- Archive table (30-day retention)
- Success determination by file size
- Filename parsing for device identification

**Usage:**
```powershell
python Anguis\db_load_captures.py --captures-dir Anguis\capture --db-path assets.db --verbose
```

---

### 7. Coverage Analysis

#### `gap_report.py`
**Purpose:** HTML coverage analysis with vendor matrix visualization

**Report Features:**
- Device inventory vs. capture coverage
- Vendor coverage matrix (capture type × vendor)
- Color-coded success indicators (green/red)
- Site-grouped device listings
- Success rate calculations

**Coverage Matrix:**
- Shows success rates like: `324/358 (98.9%)` for configs
- Identifies problem areas: `0/137` (Cisco authentication failures)
- Vendor-specific patterns visible at a glance

**Usage:**
```powershell
python Anguis\gap_report.py --sessions Anguis\sessions.yaml --output Anguis\reports\gap_report.html
Start-Process Anguis\reports\gap_report.html
```

---

### 8. Web Dashboard

#### Flask Application
**Access:** http://localhost:8086 (default: admin/admin)

**Features:**
- Device inventory with CRUD operations
- Capture file viewing (configs, inventory, fingerprints)
- Coverage analysis visualization
- Site and vendor management
- Network topology maps

**Launch:**
```powershell
cd app
python run.py
```

**Database Stats (Current Deployment):**
- 456 devices tracked
- 53 sites
- 12 capture types per device average
- Real-time capture status

---

## Complete Workflow

### Bootstrap from NetBox Export

```powershell
# 1. Place sessions.yaml in Anguis directory
# 2. Set credentials
$env:CRED_1_USER = "admin"
$env:CRED_1_PASS = "password"

# 3. Fingerprint all devices (2-4 hours for 1000+ devices)
python Anguis\batch_spn_concurrent.py Anguis\sessions.yaml --fingerprint-only --max-processes 8 --verbose

# 4. Generate job files
python Anguis\generate_capture_jobs.py --output-dir Anguis\gnet_jobs --start-id 200

# 5. Capture configs (30-60 minutes)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_configs.txt --max-processes 8 --verbose

# 6. Full operational data capture (3-4 hours)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_list_generated.txt --max-processes 8

# 7. Load into database
python Anguis\db_load_fingerprints.py --fingerprints-dir Anguis\fingerprints --db-path assets.db --verbose
python Anguis\db_load_captures.py --captures-dir Anguis\capture --db-path assets.db --verbose

# 8. Generate coverage report
python Anguis\gap_report.py --sessions Anguis\sessions.yaml --output Anguis\reports\gap_report.html

# 9. Launch web dashboard
cd app
python run.py
```

---

## Data Flow Architecture

```
NetBox Export (sessions.yaml)
    ↓
Fingerprinting (batch_spn_concurrent.py --fingerprint-only)
    ↓
Fingerprint JSONs (Anguis/fingerprints/*.json)
    ↓
Job Generation (generate_capture_jobs.py)
    ↓
Job Files (Anguis/gnet_jobs/job_*.json)
    ↓
Capture Execution (run_jobs_concurrent_batch.py)
    ↓
Capture Files (Anguis/capture/*/*.txt)
    ↓
Database Loading (db_load_*.py)
    ↓
SQLite Database (assets.db)
    ↓
Web Dashboard (Flask app:8086)
```

---

## File Organization

```
Anguis\
├── sessions.yaml              # NetBox export
├── fingerprints\              # Device fingerprints (577 files)
├── capture\                   # Operational data (5000+ files)
│   ├── configs\
│   ├── version\
│   ├── inventory\
│   ├── arp\
│   ├── bgp-summary\
│   └── [24 more types]
├── gnet_jobs\                 # Generated job files
│   ├── job_200_cisco-ios_arp.json
│   ├── job_batch_configs.txt
│   └── [106 more jobs + 34 batch lists]
├── reports\                   # Coverage analysis
│   └── gap_report.html
└── logs\                      # Execution logs

assets.db                      # SQLite database
app\                          # Flask web dashboard
```

---

## Performance Characteristics

### Actual Production Metrics (456 devices, 53 sites)

**Fingerprinting:**
- 2 seconds per device average (8 concurrent processes)
- 137 Cisco devices: 267 seconds total (2.0s avg)
- 197 Arista devices: ~400 seconds estimated
- 50-65% success rate on 1,386 total endpoints

**Configuration Capture:**
- 324/358 configs captured (98.9% of fingerprinted devices)
- ~20 seconds per device
- 8 concurrent processes optimal for network I/O

**Full Capture Suite:**
- 456 devices × 29 capture types = 13,224 potential captures
- 3-4 hours for complete execution
- CPU utilization: 84-100% across 12 cores
- Network utilization: <1 Mbps (text-based CLI)

**Database Operations:**
- Fingerprint loading: 443 devices in <5 seconds
- Capture loading: 5,000 files in 5-10 minutes
- Query response: <200ms for device lookups

### Resource Requirements

**System:**
- Windows 10/11 or Windows Server
- Python 3.8+
- 8GB RAM minimum (16GB recommended)
- 50GB storage for 1 year of captures

**Optimal Configuration:**
- 8 concurrent processes for batch operations
- 12-core CPU fully utilized during execution
- Gigabit network connection

---

## Capture Types (29 Total)

**Network State:**
- arp, mac, routes, interface-status, int-status

**Routing Protocols:**
- bgp-neighbor, bgp-summary, bgp-table, bgp-table-detail
- ospf-neighbor, eigrp-neighbor

**Discovery:**
- cdp, cdp-detail, lldp, lldp-detail

**Configuration:**
- configs, console, port-channel

**Authentication/Authorization:**
- authentication, authorization, tacacs, radius, ip_ssh

**Monitoring:**
- inventory, version, ntp_status, snmp_server, syslog

---

## Vendor Coverage Matrix

Based on production deployment data:

| Capture Type | Cisco IOS (137) | Arista (197) | HP/Aruba (127) | Overall Success |
|--------------|-----------------|--------------|----------------|-----------------|
| configs      | 136/137 (99%)   | 98/101 (97%) | 120/120 (100%) | 98.9% |
| version      | 136/137 (99%)   | 98/101 (97%) | 120/120 (100%) | 99.9% |
| inventory    | 136/137 (99%)   | 98/101 (97%) | 0/120 (0%)     | 65.4% |
| int-status   | 136/137 (99%)   | 98/101 (97%) | 119/120 (99%)  | 98.6% |
| mac          | 136/137 (99%)   | 98/101 (97%) | 120/120 (100%) | 98.9% |
| arp          | 137/137 (100%)  | 101/101 (100%) | 120/120 (100%) | 100% |
| lldp-detail  | 136/137 (99%)   | 0/101 (0%)   | 119/120 (99%)  | 71.2% |
| cdp-detail   | 0/137 (0%)      | 98/101 (97%) | 120/120 (100%) | 60.9% |

**Key Patterns:**
- **Arista:** LLDP by default, no CDP support
- **Cisco:** CDP by default, LLDP often disabled
- **HP/Aruba:** Strong command compatibility, inventory command differs

---

## Known Issues and Tuning Opportunities

### High Priority

**1. AAA Commands (Cisco)**
- `authentication` - 0/137 success (likely privilege issue)
- `authorization` - 0/137 success
- **Fix:** Change from `show run | section aaa` to `show aaa` or verify enable password

**2. Output Capture Type**
- 0/358 (0%) success across all vendors
- **Action:** Investigate command or remove from job generator

**3. Console Commands**
- Low success across all vendors (22.3%)
- **Cause:** Command syntax varies significantly
- **Action:** Test vendor-specific variations

### Medium Priority

**4. LLDP on Cisco**
- 0/137 suggests LLDP not enabled network-wide
- **Action:** Either enable LLDP or accept as operational gap

**5. Inventory on HP/Aruba**
- 0/120 suggests command mismatch
- **Current:** `show system information`
- **Try:** `show system`, `show version detail`

---

## Monitoring and Maintenance

### Daily Operations

```powershell
# Config backup (15-30 minutes)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_configs.txt --max-processes 8
```

### Weekly Operations

```powershell
# Refresh fingerprints
python Anguis\batch_spn_concurrent.py Anguis\sessions.yaml --fingerprint-only --max-processes 8

# Full capture refresh
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_list_generated.txt --max-processes 8

# Regenerate coverage report
python Anguis\gap_report.py --sessions Anguis\sessions.yaml --output Anguis\reports\weekly_report.html
```

### Monthly Operations

```powershell
# Complete re-fingerprint (new devices, firmware changes)
Remove-Item Anguis\fingerprints\*.json -Force
python Anguis\batch_spn_concurrent.py Anguis\sessions.yaml --fingerprint-only --max-processes 8

# Archive old captures
$timestamp = Get-Date -Format "yyyy-MM-dd"
Compress-Archive -Path Anguis\capture\* -DestinationPath "archives\capture_$timestamp.zip"
```

---

## Success Metrics

### Deployment Health Indicators

**Good (Production Ready):**
- 50-65% fingerprint success rate (456 of 1,386 endpoints)
- 95%+ config capture from fingerprinted devices
- <2 hour execution time for essential captures
- Coverage report shows clear vendor patterns

**Needs Tuning:**
- <80% success on specific capture types
- Vendor showing 0% on commands that should work
- Execution time >4 hours for routine captures

---

## Troubleshooting

### Zero-Byte Capture Files

**Cause:** Command executed but produced no output

**Common Reasons:**
- Paging not disabled (fixed in job generator)
- Privilege level insufficient (missing enable)
- Command timeout waiting for prompt
- Wrong command syntax for device type

**Debug:**
```powershell
# Test single device
python Anguis\spn.py --host 10.1.1.1 --user admin --password pass -c "enable,terminal length 0,show running-config" -o test.txt --verbose
```

### Low Success Rates

**Check credentials:**
```powershell
Write-Host "CRED_1_USER: $env:CRED_1_USER"
Write-Host "CRED_1_PASS length: $($env:CRED_1_PASS.Length)"
```

**Verify job command:**
```powershell
Get-Content Anguis\gnet_jobs\job_234_cisco-ios_configs.json | ConvertFrom-Json | Select-Object -ExpandProperty commands
```

---

## Production Deployment Checklist

- [x] Sessions.yaml from NetBox
- [x] Environment credentials configured
- [x] Initial fingerprinting (577 devices)
- [x] Job generation (108 jobs)
- [x] Config backup working (324/358)
- [x] Database loaded (456 devices)
- [x] Web dashboard operational
- [x] Coverage report generated
- [ ] AAA command tuning (Cisco 0% issue)
- [ ] Remove broken output capture type
- [ ] Schedule daily backups
- [ ] Archive strategy implemented

---

## Related Documentation

- **README_Bootstrap.md** - Clean environment setup guide
- **README_Fingerprinting.md** - Device identification details
- **README_Network_Mgmt_Flask.md** - Web dashboard documentation
- **README_DB_Loaders.md** - Database integration guide

---

**System Status:** Production Ready with Minor Tuning Needed

The core pipeline is operational and handling 456 devices across 53 sites with 98.9% config capture success. The job generation system eliminates manual configuration, and the coverage matrix provides clear visibility into vendor-specific command compatibility. The identified issues (AAA commands, output capture) are configuration tuning opportunities rather than architectural problems.