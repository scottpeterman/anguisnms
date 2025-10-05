# Enhanced Network Job Runner

A PyQt6-based desktop GUI for batch SSH automation jobs with vendor-specific command support. Provides an intuitive interface for executing commands across multiple network devices with advanced filtering, credential management, and real-time monitoring.

## Features

### Core Functionality
- **Batch SSH Execution**: Run commands across hundreds of devices simultaneously
- **Vendor-Specific Support**: Automatic paging disable commands for different vendors
- **Device Filtering**: Advanced filtering with wildcard support
- **Real-time Monitoring**: Live execution progress with color-coded status updates
- **Template Management**: Pre-defined command templates for common tasks
- **Credential Management**: Multiple credential systems with secure handling

### Supported Vendors
- **Cisco**: IOS/IOS-XE devices (`terminal length 0`)
- **Arista**: EOS devices (`terminal length 0`)
- **Palo Alto**: Firewalls (`set cli pager off`)
- **CloudGenix**: SD-WAN devices (`set paging off`)
- **Juniper**: JunOS devices (`set cli screen-length 0`)
- **Fortinet**: FortiGate firewalls (custom console commands)
- **Generic**: Devices without specific paging requirements

## Requirements

### Python Dependencies
```bash
pip install PyQt6 pyyaml
```

### System Requirements
- Python 3.8+
- Windows, macOS, or Linux
- Required batch scripts: `batch_spn.py`, `batch_spn_concurrent.py`
- Session file in YAML format

## Installation

1. **Clone or download** the application files
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Prepare your environment**:
   - Place session files (`.yaml`) in the application directory
   - Ensure batch scripts are available and executable
   - Create or update `command_templates.json` with your templates

## Quick Start

1. **Launch the application**:
   ```bash
   python gui2.py
   ```

2. **Load session data**:
   - Browse and select your YAML session file
   - Click "Load" to import device information

3. **Configure job**:
   - Select device vendor from dropdown
   - Choose a command template or enter custom commands
   - Set device filters (optional)
   - Configure output directory

4. **Execute**:
   - Preview devices to verify selection
   - Set credentials if needed
   - Click "Start Job" to begin execution

## User Interface Guide

### Job Configuration Tab
- **Session File**: Load YAML files containing device definitions
- **Vendor Configuration**: Select target device vendor for automatic paging setup
- **Credentials**: Set username/password or use environment variables
- **Device Filters**: Filter devices by folder, name, vendor, or device type
- **Command Configuration**: Select templates or enter custom commands
- **Execution Settings**: Choose batch script and worker limits

### Device Selection Tab
- **Device Preview**: View filtered devices before execution
- **Real-time Updates**: Color-coded status during job execution
- **Device Details**: Host, vendor, device type, folder, and credential information

### Execution Tab
- **Progress Monitoring**: Real-time execution progress bar
- **Live Logging**: Detailed execution log with timestamps
- **Status Updates**: Success/failure status for each device
- **Log Management**: Save logs to file for later analysis

### Templates Tab
- **Template Editor**: Manage command templates in JSON format
- **Template Library**: Pre-defined commands for common tasks
- **Vendor-Specific**: Templates organized by device vendor

## Configuration Files

### Session File Format (YAML)
```yaml
- folder_name: "Datacenter 1"
  sessions:
    - display_name: "fw-01"
      host: "10.1.1.1"
      port: 22
      Vendor: "Palo Alto Networks, Inc."
      DeviceType: "firewall"
      credsid: "1"
```

### Command Templates (JSON)
```json
{
  "paloalto_show_system_info": {
    "name": "Palo Alto System Info",
    "command": "show system info",
    "description": "Display Palo Alto system information",
    "vendor": "paloalto"
  }
}
```

## Credential Management

### Environment Variables
The application supports multiple credential formats:

**Per-device credentials** (recommended for batch scripts):
```bash
set CRED_1_USER=admin
set CRED_1_PASS=password123
set CRED_2_USER=netadmin
set CRED_2_PASS=different_password
```

**Global credentials** (for direct SPN usage):
```bash
set SSH_USER=admin
set SSH_PASSWORD=password123
```

### Credential Systems
- **Auto-detect**: Automatically chooses the correct format based on selected script
- **SSH_* variables**: For direct spn.py usage
- **SPN_* variables**: Legacy format support
- **Per-device CRED_***: Individual credentials per device

## Batch Script Integration

### Supported Scripts
- **batch_spn.py**: Multi-threaded execution (no verbose output)
- **batch_spn_concurrent.py**: Multi-process execution (with verbose output)

### Execution Parameters
- **Max Workers/Processes**: Configurable parallelism
- **Dry Run**: Preview mode without actual execution
- **Verbose Output**: Detailed logging (when supported)
- **Output Directory**: Organized results by job type

## Advanced Features

### Device Filtering
Use wildcards and patterns to target specific devices:
- **Folder filter**: `*datacenter*` matches any folder containing "datacenter"
- **Name filter**: `fw-*` matches devices starting with "fw-"
- **Vendor filter**: `palo*` matches Palo Alto devices
- **Device type**: Exact match on device type field

### Vendor-Specific Commands
Commands are automatically enhanced with vendor-specific paging disable:
- **Input**: `show system info`
- **Final command**: `set cli pager off,show system info` (for Palo Alto)

### Template Management
- **Auto-vendor detection**: Templates automatically set the correct vendor
- **Bulk operations**: Import/export template libraries
- **Validation**: Template format validation with error reporting

## Troubleshooting

### Common Issues

**"Final Command" box empty**:
- Check if vendor is selected correctly
- Verify command template has proper vendor field
- Restart application if UI state is corrupted

**"Missing credentials" error**:
- Verify environment variables are set correctly
- Check credential ID format matches your session file
- Use "Per-device CRED_*" credential system for batch scripts

**"Unrecognized arguments" error**:
- Ensure selected batch script exists and is executable
- Verify script supports the parameters being passed
- Check script compatibility with execution settings

**No devices found**:
- Verify session file format and loading
- Check device filters - clear filters to see all devices
- Use "Show Available Values" to see filterable options

### Debug Mode
Enable detailed logging by checking the execution log tab. All operations are logged with timestamps for troubleshooting.

### Log Files
- **Execution logs**: Available in the GUI and can be saved to file
- **Device output**: Stored in `capture/{output_directory}/` subdirectories
- **Error logs**: Individual `.log` files for failed devices

## File Structure

```
network-job-runner/
├── gui2.py                    # Main application
├── command_templates.json     # Command template library
├── sessions.yaml             # Device session data
├── batch_spn.py              # Multi-threaded batch script
├── batch_spn_concurrent.py   # Multi-process batch script
├── capture/                  # Output directory
│   ├── version/              # Version command outputs
│   ├── config/               # Configuration backups
│   └── inventory/            # Hardware inventory
└── README.md                 # This file
```

## Examples

### Get Version Information
1. Load session file with network devices
2. Select "Cisco" vendor
3. Choose "Cisco Version Information" template
4. Filter devices: `--vendor cisco*`
5. Set output directory: `version`
6. Execute job

### Backup Configurations
1. Select "Arista" vendor
2. Use template: "Arista Running Config" 
3. Filter by folder: `*datacenter*`
4. Set output directory: `configs`
5. Use multi-process script for faster execution

### Custom Commands
1. Select appropriate vendor
2. Enter custom commands: `show ip route,show arp table`
3. Preview final command with automatic paging disable
4. Execute across filtered device set

## Support and Contributions

### Getting Help
- Check the execution log for detailed error information
- Verify batch script compatibility and arguments
- Ensure credential format matches your execution environment

### Template Contributions
Templates can be shared by exporting the `command_templates.json` file. Include vendor field for automatic vendor detection.

## Version History

### v1.2.0 (Current)
- Enhanced vendor support with automatic paging disable
- Improved credential management with multiple systems
- Real-time execution monitoring with color-coded status
- Advanced device filtering with wildcard support
- Template management with vendor auto-detection
- Force cancellation for stuck jobs

### v1.1.0
- Basic GUI implementation
- Template system
- Device filtering
- Batch script integration

### v1.0.0
- Initial release
- Core SSH automation functionality