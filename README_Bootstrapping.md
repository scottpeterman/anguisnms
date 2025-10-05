<artifact identifier="bootstrap-guide" type="text/markdown" title="Anguis Bootstrap Guide - Windows Environment">
# Anguis Bootstrap Guide - Clean Environment Setup

Starting fresh with only a NetBox-exported `sessions.yaml` file. This guide gets you from zero to full network inventory and configuration backups.

---

## Prerequisites

### System Requirements
- Windows 10/11 or Windows Server
- Python 3.8 or higher
- 4GB+ RAM (8GB recommended for large networks)
- Network access to target devices

### Python Environment

```powershell
# Verify Python version
python --version  # Should be 3.8+

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install paramiko pyyaml networkx textfsm
```

### Directory Structure

```powershell
# Create required directories
New-Item -ItemType Directory -Force -Path Anguis\fingerprints
New-Item -ItemType Directory -Force -Path Anguis\capture
New-Item -ItemType Directory -Force -Path Anguis\logs
New-Item -ItemType Directory -Force -Path Anguis\reports
New-Item -ItemType Directory -Force -Path Anguis\gnet_jobs
```

---

## Step 1: Prepare Sessions File

### From NetBox Export

Place your NetBox-exported `sessions.yaml` in the `Anguis` directory:

```
project_root\
├── Anguis\
│   ├── sessions.yaml       # Your NetBox export
│   ├── fingerprints\       # Will be populated
│   ├── capture\            # Will be populated
│   └── gnet_jobs\          # Will be populated
└── assets.db               # Optional - web dashboard database
```

### Verify Sessions File Format

```powershell
# Check file exists and is readable
Get-Content Anguis\sessions.yaml -Head 20

# Count total devices
(Select-String -Path Anguis\sessions.yaml -Pattern "display_name:").Count
```

Expected format:
```yaml
- folder_name: "Site Name"
  sessions:
    - display_name: "device-name-01"
      host: "10.1.1.1"
      port: 22
      vendor: "Cisco"
      credential_id: 1
```

---

## Step 2: Set Up Credentials

### Environment Variables Method (Recommended)

```powershell
# Set credentials for batch operations
$env:CRED_1_USER = "admin"
$env:CRED_1_PASS = "your-password"
$env:CRED_2_USER = "netadmin"
$env:CRED_2_PASS = "other-password"

# Verify (shows username, password length only)
Write-Host "CRED_1_USER: $env:CRED_1_USER"
Write-Host "CRED_1_PASS length: $($env:CRED_1_PASS.Length) characters"
```

### PowerShell Profile (Persistent)

```powershell
# Check if profile exists
Test-Path $PROFILE

# Create profile directory if needed
New-Item -ItemType Directory -Force -Path (Split-Path $PROFILE)

# Edit PowerShell profile
notepad $PROFILE

# Add these lines to profile:
$env:CRED_1_USER = "admin"
$env:CRED_1_PASS = "your-password"
$env:CRED_2_USER = "netadmin"
$env:CRED_2_PASS = "other-password"

# Save and reload profile
. $PROFILE
```

### Security Note
Never commit credentials to git. Add to `.gitignore`:
```
.env
credentials.txt
*.pwd
$PROFILE
```

---

## Step 3: Initial Device Fingerprinting

This discovers what devices you can actually reach and identifies their vendor/model/version.

```powershell
# Start fingerprinting (will take 2-4 hours for 1000+ devices)
python Anguis\batch_spn_concurrent.py Anguis\sessions.yaml --fingerprint-only --max-processes 8 --verbose

# Monitor progress in another PowerShell window
while ($true) {
    Clear-Host
    $count = (Get-ChildItem Anguis\fingerprints\*.json -ErrorAction SilentlyContinue).Count
    $total = (Select-String -Path Anguis\sessions.yaml -Pattern "display_name:").Count
    $percent = [math]::Round($count/$total*100, 1)
    Write-Host "Fingerprints: $count / $total ($percent%)"
    Write-Host "Press Ctrl+C to stop monitoring"
    Start-Sleep -Seconds 10
}
```

### Expected Results

```
Total devices in sessions.yaml: 1386
Successful fingerprints: ~700-900 (50-65%)
Failed connections: ~400-500 (firewalls, servers, unreachable)
```

**Common failure reasons:**
- SSH not enabled
- Wrong credentials (check environment variables)
- Firewall blocking access
- Device offline or unreachable
- Wrong IP address in NetBox

### Verify Fingerprint Quality

```powershell
# Check a sample fingerprint
Get-Content Anguis\fingerprints\device-name.json | ConvertFrom-Json | Format-List

# Count by vendor
Get-ChildItem Anguis\fingerprints\*.json | ForEach-Object {
    (Get-Content $_.FullName | ConvertFrom-Json).Vendor
} | Group-Object | Sort-Object Count -Descending
```

---

## Step 4: Generate Capture Jobs

Create vendor-specific job files for automated data collection.

```powershell
# Generate all job files (takes ~5 seconds)
python Anguis\generate_capture_jobs.py --output-dir Anguis\gnet_jobs --start-id 200

# Verify generation
(Get-ChildItem Anguis\gnet_jobs\job_*.json).Count  # Should be ~108 files

# Check batch lists created
Get-ChildItem Anguis\gnet_jobs\job_batch_*.txt | Select-Object Name, Length
```

This creates:
- **108 job files** (29 capture types × 4 vendors - some skipped combinations)
- **Master batch list** (`job_batch_list_generated.txt`) - all jobs
- **Vendor batch lists** - `job_batch_cisco_ios.txt`, `job_batch_arista.txt`, etc.
- **Capture type lists** - `job_batch_configs.txt`, `job_batch_version.txt`, etc.

### Verify Job Configuration

```powershell
# Check what's in the configs batch
Get-Content Anguis\gnet_jobs\job_batch_configs.txt

# Inspect a job file
Get-Content Anguis\gnet_jobs\job_234_cisco-ios_configs.json | ConvertFrom-Json | Format-List
```

---

## Step 5: Configuration Backup

Capture running configs from all fingerprinted devices.

```powershell
# Backup all configs (30-60 minutes)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_configs.txt --max-processes 8 --verbose

# Monitor progress in another window
while ($true) {
    Clear-Host
    $count = (Get-ChildItem Anguis\capture\configs\*.txt -ErrorAction SilentlyContinue).Count
    Write-Host "Configs captured: $count"
    Write-Host "Press Ctrl+C to stop monitoring"
    Start-Sleep -Seconds 15
}
```

### Expected Output

```
Anguis\capture\configs\
├── device-01_running-config.txt
├── device-02_running-config.txt
├── device-03_running-config.txt
└── ... (300-500 files expected)
```

### Verify Captures

```powershell
# Check capture file sizes
Get-ChildItem Anguis\capture\configs\*.txt | Measure-Object -Property Length -Sum -Average

# Find suspiciously small configs (potential failures)
Get-ChildItem Anguis\capture\configs\*.txt | Where-Object {$_.Length -lt 1000} | Select-Object Name, Length

# View a sample config
Get-Content (Get-ChildItem Anguis\capture\configs\*.txt | Select-Object -First 1).FullName -Head 50
```

---

## Step 6: Full Operational Data Capture

Collect comprehensive network state information.

### Essential Captures (Fast - 60-90 minutes)

```powershell
# Core operational data - run these in order
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_version.txt --max-processes 8
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_inventory.txt --max-processes 8
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_interface-status.txt --max-processes 8
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_mac.txt --max-processes 8
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_arp.txt --max-processes 8
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_lldp-detail.txt --max-processes 8
```

### Complete Capture Suite (Comprehensive - 3-4 hours)

```powershell
# All 108 jobs (29 capture types × ~4 vendors each)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_list_generated.txt --max-processes 8 --verbose
```

### Monitor All Captures

```powershell
# Summary of all capture types
Get-ChildItem Anguis\capture\* -Directory | ForEach-Object {
    $count = (Get-ChildItem $_.FullName\*.txt -ErrorAction SilentlyContinue).Count
    [PSCustomObject]@{
        CaptureType = $_.Name
        Files = $count
    }
} | Sort-Object Files -Descending | Format-Table -AutoSize
```

### Capture Directory Structure

```
Anguis\capture\
├── configs\           # Running configurations
├── version\           # Software versions
├── interface-status\  # Interface states
├── inventory\         # Hardware inventory
├── mac\              # MAC address tables
├── arp\              # ARP tables
├── cdp\              # CDP neighbors
├── cdp-detail\       # CDP neighbors (detailed)
├── lldp\             # LLDP neighbors
├── lldp-detail\      # LLDP neighbors (detailed)
├── bgp-summary\      # BGP status
├── ospf-neighbor\    # OSPF adjacencies
├── port-channel\     # LAG/trunk status
├── routes\           # Routing tables
├── authentication\   # AAA authentication config
├── authorization\    # AAA authorization config
├── tacacs\           # TACACS+ config
├── radius\           # RADIUS config
├── ntp_status\       # NTP status
├── syslog\           # Syslog config
└── ... (10 more types)
```

---

## Step 7: Coverage Analysis

Generate reports showing what data was successfully captured.

```powershell
# Generate gap analysis report
python Anguis\gap_report.py --sessions Anguis\sessions.yaml --output Anguis\reports\gap_report.html

# Open in default browser
Start-Process Anguis\reports\gap_report.html
```

**Report shows:**
- Total devices vs. captured devices per type
- Success rates by vendor and capture type (matrix view)
- Devices with missing data
- Perfect coverage devices (green) vs. zero coverage (red)
- Site-grouped device listing

### Alternative Report Formats

```powershell
# Text summary to console
python Anguis\gap_report.py --sessions Anguis\sessions.yaml --output Anguis\reports\gap_report.html --verbose
```

---

## Step 8: Load into Web Dashboard (Optional)

If using the Flask web interface for asset tracking:

```powershell
# Load fingerprints into database
python Anguis\db_load_fingerprints.py --fingerprints-dir Anguis\fingerprints --db-path assets.db --verbose

# Load captures into database (current + archive pattern)
python Anguis\db_load_capture.py --captures-dir Anguis\capture --db-path assets.db --verbose

# Launch web interface
cd app
python run.py
# Access at http://localhost:8086
# Default credentials: admin / admin
```

---

## Maintenance Schedule

### Daily Operations (Automated via Task Scheduler)

```powershell
# Quick config backup (15-30 minutes)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_configs.txt --max-processes 8
```

**Setup Windows Task Scheduler:**
```powershell
# Create daily backup script
@"
cd C:\path\to\project
.venv\Scripts\activate
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_configs.txt --max-processes 8
"@ | Out-File -Encoding ASCII daily_backup.ps1

# Register scheduled task (run as your user account)
# Use Task Scheduler GUI or schtasks.exe
```

### Weekly Operations

```powershell
# Refresh fingerprints for changed devices (firmware updates, new devices)
python Anguis\batch_spn_concurrent.py Anguis\sessions.yaml --fingerprint-only --max-processes 8

# Full operational data refresh (all 29 capture types)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_list_generated.txt --max-processes 8

# Regenerate coverage report
python Anguis\gap_report.py --sessions Anguis\sessions.yaml --output Anguis\reports\weekly_report.html
```

### Monthly Operations

```powershell
# Complete re-fingerprint (captures firmware changes, new devices)
Remove-Item Anguis\fingerprints\*.json -Force
python Anguis\batch_spn_concurrent.py Anguis\sessions.yaml --fingerprint-only --max-processes 8

# Archive old captures (manual - before cleanup)
$timestamp = Get-Date -Format "yyyy-MM-dd"
Compress-Archive -Path Anguis\capture\* -DestinationPath "archives\capture_$timestamp.zip"

# Clean old captures if needed
Remove-Item Anguis\capture\*\*.txt -Force

# Regenerate monthly report
python Anguis\gap_report.py --sessions Anguis\sessions.yaml --output Anguis\reports\monthly_report_$(Get-Date -Format 'yyyy-MM').html
```

---

## Troubleshooting

### Low Fingerprint Success Rate (<40%)

```powershell
# Test single device manually
python Anguis\spn.py --host 10.1.1.1 --user admin --password yourpass --fingerprint --verbose

# Check if credentials are set
if ($env:CRED_1_USER) {
    Write-Host "CRED_1_USER is set: $env:CRED_1_USER"
} else {
    Write-Host "WARNING: CRED_1_USER not set!" -ForegroundColor Red
}

# Test SSH connectivity (requires OpenSSH client)
Test-NetConnection -ComputerName 10.1.1.1 -Port 22
```

### Job Failures

```powershell
# Check job configuration
Get-Content Anguis\gnet_jobs\job_234_cisco-ios_configs.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

# Verify vendor filter matches fingerprints
Select-String -Path "Anguis\fingerprints\*.json" -Pattern '"Vendor": "Cisco"' | Measure-Object

# Test single device directly
python Anguis\spn.py --host 10.1.1.1 --user admin --password yourpass -c "show running-config" -o test_output.txt --verbose
```

### Performance Issues

```powershell
# Reduce concurrent processes if hitting system limits
--max-processes 4  # Instead of 8

# Process smaller batches (single vendor)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_cisco_ios.txt --max-processes 6

# Check system resource usage
Get-Process python | Select-Object CPU, WorkingSet, Id
```

### Missing Capture Files

```powershell
# Check if capture directory was created
Test-Path Anguis\capture\configs

# Verify job actually ran
Get-Content Anguis\gnet_jobs\job_234_cisco-ios_configs.json | ConvertFrom-Json | Select-Object -ExpandProperty commands

# Check for error logs
Get-ChildItem Anguis\logs\*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

---

## Quick Reference Commands

### Status Checks

```powershell
# Comprehensive status check
$sessions = (Select-String -Path Anguis\sessions.yaml -Pattern "display_name:").Count
$fingerprints = (Get-ChildItem Anguis\fingerprints\*.json -ErrorAction SilentlyContinue).Count
$configs = (Get-ChildItem Anguis\capture\configs\*.txt -ErrorAction SilentlyContinue).Count

Write-Host "=" * 50
Write-Host "Anguis Status Summary"
Write-Host "=" * 50
Write-Host "Total devices in sessions.yaml: $sessions"
Write-Host "Successful fingerprints: $fingerprints ($([math]::Round($fingerprints/$sessions*100,1))%)"
Write-Host "Config backups captured: $configs ($([math]::Round($configs/$fingerprints*100,1))% of fingerprinted)"
Write-Host "=" * 50
```

### Cleanup Operations

```powershell
# Start fresh (keeps sessions.yaml and job files)
Remove-Item Anguis\fingerprints\*.json -Force
Remove-Item Anguis\capture\*\*.txt -Recurse -Force
Remove-Item Anguis\logs\*.log -Force

# Complete reset (WARNING: Deletes everything except sessions.yaml)
Remove-Item Anguis\fingerprints\*.json -Force
Remove-Item Anguis\capture\*\*.txt -Recurse -Force
Remove-Item Anguis\gnet_jobs\job_*.json -Force
Remove-Item Anguis\gnet_jobs\job_batch_*.txt -Force
Remove-Item Anguis\logs\*.log -Force
Remove-Item assets.db -Force
Remove-Item Anguis\reports\*.html -Force
```

### Selective Processing

```powershell
# Single vendor (all capture types for Cisco IOS)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_cisco_ios.txt --max-processes 8

# Single capture type (all vendors)
python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\job_batch_version.txt --max-processes 8

# Custom job list (create your own batch file)
@"
job_234_cisco-ios_configs.json
job_236_arista_configs.json
job_268_cisco-ios_mac.json
"@ | Out-File -Encoding ASCII Anguis\gnet_jobs\custom_jobs.txt

python Anguis\run_jobs_concurrent_batch.py Anguis\gnet_jobs\custom_jobs.txt --max-processes 8
```

### Batch List Reference

```powershell
# View all available batch lists
Get-ChildItem Anguis\gnet_jobs\job_batch_*.txt | Select-Object Name, @{N='Jobs';E={(Get-Content $_.FullName).Count}}

# Common batch lists:
# job_batch_configs.txt          - All vendor configs (4 jobs)
# job_batch_version.txt          - All vendor versions (4 jobs)
# job_batch_cisco_ios.txt        - All Cisco IOS captures (~29 jobs)
# job_batch_aruba.txt            - All HP/Aruba captures (~23 jobs)
# job_batch_list_generated.txt   - Complete suite (~108 jobs)
```

---

## File Manifest

### Required Core Files
All scripts should be in the `Anguis\` directory:

- `sessions.yaml` - Device inventory from NetBox
- `batch_spn_concurrent.py` - Batch fingerprinting/capture engine
- `run_jobs_concurrent_batch.py` - Job orchestration system
- `generate_capture_jobs.py` - Job file generator
- `gap_report.py` - Coverage analysis reporting
- `spn.py` - SSH execution engine
- `device_fingerprint.py` - Device identification system
- `ssh_client.py` - SSH client implementation
- `tfsm_fire.py` - TextFSM template engine
- `tfsm_templates.db` - Template database (100+ templates)

### Optional Components
- `db_load_fingerprints.py` - Database loader for fingerprints
- `db_load_captures.py` - Database loader for captures
- `app\run.py` - Flask web dashboard
- `map_to_session.py` - Topology to session converter

### Generated Files
- `Anguis\fingerprints\*.json` - Device fingerprint data (700-900 files)
- `Anguis\capture\*\*.txt` - Operational data captures (5000-15000 files)
- `Anguis\gnet_jobs\job_*.json` - Capture job configurations (108 files)
- `Anguis\gnet_jobs\job_batch_*.txt` - Batch execution lists (34 files)
- `Anguis\reports\*.html` - Analysis reports
- `Anguis\logs\*.log` - Execution logs
- `assets.db` - SQLite database (if using web dashboard)

---

## Success Metrics

After bootstrap completion, you should have:

- **700-900 fingerprints** (50-65% of ~1400 devices) ✓
- **300-500 configs** (50-70% of fingerprinted devices) ✓
- **Coverage report** showing vendor/capture success rates ✓
- **Automated jobs** ready for daily/weekly runs ✓

### Understanding Success Rates

**50-65% fingerprint rate is normal and expected:**
- Network devices (switches/routers): ~90% success
- Firewalls with restricted SSH: ~30% success  
- Servers (Linux/Windows): ~50% success
- IoT/Printers/Phones: ~10% success
- Offline/unreachable devices: 0% success

**The 50-65% represents reachable, manageable infrastructure** - exactly what you want to automate.

---

## Next Steps

After successful bootstrap:

1. **Schedule daily config backups** via Windows Task Scheduler
2. **Set up weekly full captures** for comprehensive state collection
3. **Enable web dashboard** for visual inventory management
4. **Review coverage reports** to identify credential or access issues
5. **Tune vendor filters** based on actual device fingerprints
6. **Add custom capture types** for specialized monitoring needs

---

## Support and Documentation

- **README.md** - Platform overview
- **README_Pipeline.md** - Data collection pipeline details
- **README_Fingerprinting.md** - Device identification system
- **README_Maps_Pipeline.md** - Network topology mapping
- **README_Network_Mgmt_Flask.md** - Web dashboard guide
- **README_DB_Loaders.md** - Database loading utilities

For issues or questions, review the specialized documentation for your specific component.
</artifact>

I've updated the bootstrap guide as an artifact with correct Windows path syntax using backslashes (`\`) throughout. Key changes:

1. **All paths now use `Anguis\` prefix** - matches your actual directory structure
2. **Corrected database loader command** - `python Anguis\db_load_fingerprints.py --fingerprints-dir Anguis\fingerprints --db-path assets.db --verbose`
3. **Consistent Windows backslash syntax** throughout all commands
4. **Project structure clarified** - `Anguis\` subdirectory with `assets.db` at root level
5. **All file references updated** - sessions.yaml, capture directories, etc.

The guide now accurately reflects your Windows environment with the `Anguis` subdirectory structure.