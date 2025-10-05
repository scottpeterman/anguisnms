# Network Mapping and Enhancement Pipeline

A comprehensive solution for automated network discovery, topology mapping, and visualization enhancement across multiple sites. This pipeline discovers network topologies via CDP/LLDP, generates enhanced visualizations with vendor-specific icons, and produces multiple output formats suitable for both web display and engineering workflows.

## Architecture Overview

```
┌─────────────────────┐
│   sessions.yaml     │  Device inventory with folders/sites
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│    sc_run3.py       │  Parallel network discovery wrapper
│  (Discovery Phase)  │  - Selects seed devices per site
└──────────┬──────────┘  - Runs secure_cartography in parallel
           │             - Creates base JSON topology
           v
    ┌──────────────┐
    │  maps/       │     Folder structure:
    │  ├─ site1/   │     maps/site1/site1.json
    │  ├─ site2/   │     maps/site2/site2.json
    │  └─ site3/   │     maps/site3/site3.json
    └──────┬───────┘
           │
           v
┌─────────────────────────────┐
│   enhance_all_maps.py       │  Batch enhancement wrapper
│  (Enhancement Phase)        │  - Scans maps/ for JSON files
└──────────┬──────────────────┘  - Calls enhancer in parallel
           │
           v
┌─────────────────────────────┐
│   sc_enhance_map3.py        │  Per-site enhancement
│  (Per-Site Processor)       │  - Reads JSON topology
└──────────┬──────────────────┘  - Generates 3 output formats
           │
           v
    ┌─────────────────────────────────────────┐
    │  Enhanced Output per Site:              │
    │  ├─ site.graphml  (yEd, detailed)       │
    │  ├─ site.drawio   (Draw.io, detailed)   │
    │  └─ site.svg      (Web display, clean)  │
    └─────────────────────────────────────────┘
```

## Components

### 1. sc_run3.py - Concurrent Discovery Wrapper

**Purpose**: Orchestrates parallel network discovery across multiple sites using secure_cartography.

**Key Features**:
- Loads site inventory from `sessions.yaml`
- Intelligently selects seed devices (prefers core, spine, distribution switches)
- Runs discoveries in parallel with configurable worker count
- Prevents cross-site discovery contamination
- Real-time output streaming with site prefixes
- Comprehensive error handling and reporting

**Input**: `sessions.yaml` with site folders and device sessions  
**Output**: JSON topology files in `maps/<site>/` directories

### 2. enhance_all_maps.py - Batch Enhancement Wrapper

**Purpose**: Scans the maps directory structure and enhances all JSON topology files in parallel.

**Key Features**:
- Recursive directory scanning for JSON files
- Parallel enhancement with configurable workers
- Site filtering for selective processing
- Dry-run mode for validation
- Comprehensive success/failure reporting

**Input**: Directory tree under `./maps/`  
**Output**: Enhanced GraphML, DrawIO, and SVG files per site

### 3. sc_enhance_map3.py - Single-Site Enhancement

**Purpose**: Converts a single JSON topology into three enhanced visualization formats.

**Key Features**:
- **GraphML Export**: yEd-compatible with vendor icons and full topology
- **DrawIO Export**: Draw.io-compatible with vendor icons and full topology
- **SVG Export**: Mermaid-based rendering for web display
- Separate endpoint control for GraphML/DrawIO vs SVG
- NetworkX-based topology analysis (degree, betweenness, clustering)
- Automatic icon library detection

**Input**: Single JSON topology file  
**Output**: `.graphml`, `.drawio`, `.svg` files

## Output Formats

### GraphML (Engineering View)
- **Audience**: Network engineers using yEd
- **Content**: Complete topology with all devices
- **Features**: Vendor-specific icons, detailed labels, hierarchical layout
- **Use Case**: Network planning, troubleshooting, documentation

### DrawIO (Engineering View)
- **Audience**: Engineers/architects using Draw.io
- **Content**: Complete topology with all devices
- **Features**: Vendor-specific icons, editable diagrams
- **Use Case**: Architecture diagrams, presentations, collaborative editing

### SVG (Web/Presentation View)
- **Audience**: Stakeholders, web interfaces, dashboards
- **Content**: Core infrastructure only (endpoints optional)
- **Features**: Clean Mermaid rendering, dark/light themes, interactive
- **Use Case**: Web dashboards, executive presentations, quick reference

## Workflow Separation: Clean vs Detailed Views

The pipeline provides intelligent separation between high-level and detailed views:

**For Web Display (SVG with `--svg-no-endpoints`)**:
- Shows only core network infrastructure
- Hides endpoint devices (access switches, phones, workstations)
- Clean, readable topology suitable for dashboards
- Example: 100-device network reduced to ~15 core devices

**For Engineering Work (GraphML/DrawIO)**:
- Shows complete topology with all discovered devices
- Full detail including endpoints, interface labels, IP addresses
- Suitable for troubleshooting and network planning

This separation is crucial for large networks where the full topology would be unreadable in a web view.

## Installation

### Prerequisites
```bash
# Python 3.9+
pip install pyyaml networkx PyQt6 PyQt6-WebEngine

# secure_cartography package
pip install secure_cartography

# Or install from local development
pip install -e /path/to/secure_cartography
```

### Icon Library
Place vendor icon library in one of these locations (auto-detected):
- `./icons_lib/`
- `/path/to/secure_cartography/icons_lib/`
- Custom path via `--icons-dir`

## Usage

### Full Pipeline (Discovery + Enhancement)

```bash
# Step 1: Discover all sites (parallel)
python sc_run3.py \
    --username admin \
    --password secret \
    --workers 10 \
    --output-dir ./maps

# Step 2: Enhance all discovered maps (parallel)
python enhance_all_maps.py \
    --svg-no-endpoints \
    --workers 10
```

### Discovery Options (sc_run3.py)

```bash
# Basic discovery
python sc_run3.py --username admin --password secret

# High-performance parallel discovery
python sc_run3.py \
    --username admin \
    --password secret \
    --workers 10 \
    --process-timeout 600

# Filter specific sites
python sc_run3.py \
    --username admin \
    --password secret \
    --filter "datacenter,hq" \
    --workers 4

# Dry run (show what would be discovered)
python sc_run3.py \
    --username admin \
    --password secret \
    --dry-run

# With alternate credentials
python sc_run3.py \
    --username admin \
    --password secret \
    --alternate-username backup_admin \
    --alternate-password backup_pass \
    --workers 8
```

### Enhancement Options

#### Batch Enhancement (enhance_all_maps.py)

```bash
# Basic enhancement - all formats
python enhance_all_maps.py

# Clean SVGs for web, detailed GraphML/DrawIO
python enhance_all_maps.py --svg-no-endpoints --workers 10

# Exclude endpoints from everything
python enhance_all_maps.py --no-endpoints --svg-no-endpoints --workers 10

# Light theme SVGs
python enhance_all_maps.py --svg-no-endpoints --light-mode

# Skip SVG for faster processing (GraphML/DrawIO only)
python enhance_all_maps.py --skip-svg --workers 14

# Filter specific sites
python enhance_all_maps.py --filter "branch" --workers 4

# Custom layouts
python enhance_all_maps.py \
    --layout tree \
    --svg-layout LR \
    --svg-no-endpoints
```

#### Single-Site Enhancement (sc_enhance_map3.py)

```bash
# Basic enhancement
python sc_enhance_map3.py maps/site1/site1.json

# Clean SVG, full GraphML/DrawIO
python sc_enhance_map3.py maps/site1/site1.json --svg-no-endpoints

# Custom layouts and themes
python sc_enhance_map3.py maps/site1/site1.json \
    --layout balloon \
    --svg-layout LR \
    --light-mode

# Skip SVG generation
python sc_enhance_map3.py maps/site1/site1.json --skip-svg
```

## Configuration

### sessions.yaml Structure

```yaml
- folder_name: "Datacenter East | Primary"
  sessions:
    - display_name: "dc-east-core-01"
      host: "10.1.1.1"
      port: 22
    - display_name: "dc-east-sw-02"
      host: "10.1.1.2"
      port: 22

- folder_name: "Branch Office - West"
  sessions:
    - display_name: "branch-west-sw-01"
      host: "192.168.1.1"
      port: 22
```

### Device Selection Priority

The discovery wrapper selects seed devices based on naming patterns (in order):
1. `core` - Core routers/switches
2. `spine` - Spine switches (data center)
3. `cr` - Campus routers
4. `-sw-` - Distribution/aggregation switches
5. `-swl` - Access layer switches

### Layout Algorithms

**GraphML/DrawIO Layouts**:
- `tree` (default) - Hierarchical top-down layout
- `balloon` - Radial layout from center
- `grid` - Grid-based layout

**SVG Layouts (Mermaid)**:
- `TD` (default) - Top-down flowchart
- `LR` - Left-right flowchart

## Performance Considerations

### Processing Time

**Discovery Phase** (sc_run3.py):
- Small site (<10 devices): ~30-60 seconds
- Medium site (10-50 devices): ~90-180 seconds
- Large site (50-100 devices): ~180-300 seconds

**Enhancement Phase** (enhance_all_maps.py):
- GraphML + DrawIO only: ~5-10 seconds per site
- With SVG (Qt WebEngine): ~20-35 seconds per site

### Recommended Worker Counts

Based on processing 295 sites on 14-core system:

**Discovery (CPU + Network I/O)**:
```bash
--workers 8-10  # Balanced for network I/O and CPU
```

**Enhancement (CPU + Memory)**:
```bash
# With SVG (memory intensive due to Qt)
--workers 8-10

# GraphML/DrawIO only (CPU bound)
--workers 12-14
```

### Optimization Strategies

**For Regular 4-Hour Collection Cycles**:
```bash
# Discovery: ~60-90 minutes for 295 sites
python sc_run3.py --username admin --password secret --workers 10

# Enhancement: ~120-150 minutes for 295 sites
python enhance_all_maps.py --svg-no-endpoints --workers 10

# Total: ~3-4 hours (fits within 4-hour window)
```

**For Faster Iterations**:
```bash
# Discovery: unchanged (~60-90 min)
python sc_run3.py --username admin --password secret --workers 10

# Skip SVG initially (~10-20 min)
python enhance_all_maps.py --skip-svg --workers 14

# Generate SVGs on-demand for specific sites
python enhance_all_maps.py --filter "datacenter,hq" --workers 4
```

## File Organization

```
project/
├── sc_run3.py                  # Discovery orchestrator
├── enhance_all_maps.py         # Batch enhancement wrapper
├── sc_enhance_map3.py          # Single-site enhancer
├── sessions.yaml               # Site/device inventory
├── icons_lib/                  # Vendor icon library
│   ├── cisco/
│   ├── juniper/
│   └── generic/
└── maps/                       # Output directory
    ├── site1/
    │   ├── site1.json          # Topology data
    │   ├── site1.graphml       # yEd format
    │   ├── site1.drawio        # Draw.io format
    │   └── site1.svg           # Web display
    ├── site2/
    │   └── ...
    └── site3/
        └── ...
```

## Troubleshooting

### Common Issues

**"charmap codec can't encode" errors**:
- Cause: Unicode symbols in output on Windows
- Solution: Encoding issues resolved in current version

**SVG shows "No data loaded"**:
- Cause: Qt WebEngine rendering failed or timeout
- Solution: Check timeout settings, verify PyQt6-WebEngine installed

**Empty or missing GraphML/DrawIO files**:
- Cause: Icon library not found
- Solution: Verify `icons_lib/` path or use `--icons-dir`

**Cross-site device discovery**:
- Cause: Site exclusion not configured
- Solution: sc_run3.py automatically excludes other site names

### Debug Output

```bash
# Enable verbose logging
python sc_run3.py --username admin --password secret --save-debug-info

# Test single site
python sc_run3.py --filter "testsite" --username admin --password secret

# Dry run to validate configuration
python sc_run3.py --dry-run
python enhance_all_maps.py --dry-run
```

## Integration Example

### Automated 4-Hour Collection Cycle

```bash
#!/bin/bash
# collect_and_enhance.sh

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="./logs"
mkdir -p $LOG_DIR

# Step 1: Discovery
echo "[$TIMESTAMP] Starting network discovery..."
python sc_run3.py \
    --username admin \
    --password secret \
    --workers 10 \
    --output-dir ./maps \
    > "$LOG_DIR/discovery_$TIMESTAMP.log" 2>&1

# Step 2: Enhancement
echo "[$TIMESTAMP] Starting map enhancement..."
python enhance_all_maps.py \
    --svg-no-endpoints \
    --workers 10 \
    > "$LOG_DIR/enhancement_$TIMESTAMP.log" 2>&1

echo "[$TIMESTAMP] Collection complete!"
```

### Scheduled via Cron (Linux/macOS)

```bash
# Run every 4 hours
0 */4 * * * /path/to/project/collect_and_enhance.sh
```

### Scheduled via Task Scheduler (Windows)

```powershell
# PowerShell wrapper
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = ".\logs"
New-Item -ItemType Directory -Force -Path $logDir

python sc_run3.py --username admin --password secret --workers 10 `
    > "$logDir\discovery_$timestamp.log" 2>&1

python enhance_all_maps.py --svg-no-endpoints --workers 10 `
    > "$logDir\enhancement_$timestamp.log" 2>&1
```

## Future Enhancements

Potential improvements for consideration:
- Integrated mode: `sc_run3.py --enhance-maps` for single-step operation
- Incremental enhancement: Only regenerate changed topologies
- API endpoint: Serve maps via REST API for web dashboard
- Diff reporting: Compare topologies between collection cycles
- Alerting: Notify on topology changes or discovery failures

## License

Refer to secure_cartography package license for underlying discovery functionality.