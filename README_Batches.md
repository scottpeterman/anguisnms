# Single-Threaded Batch SSH Runner

## Overview

This is a simplified, single-threaded version of the batch SSH automation wrapper. It executes commands sequentially across multiple devices from YAML session files, making it easier to debug issues and observe output in real-time.

## Key Differences from Multi-Threaded Version

- **Sequential Execution**: Devices are processed one at a time, not in parallel
- **Real-time Output**: You can see each device's progress as it happens
- **Simpler Debugging**: No thread synchronization issues to complicate troubleshooting
- **Lower Resource Usage**: Uses less system resources, suitable for smaller batches
- **Easier to Stop**: Ctrl+C cleanly stops between devices

## When to Use Single-Threaded

- **Development & Testing**: When developing new command sequences
- **Troubleshooting**: When you need to see exactly what's happening with each device
- **Rate-Limited Networks**: When the target network has connection limits
- **Small Batches**: When processing fewer than 10-15 devices
- **Resource-Constrained Systems**: On systems with limited CPU/memory

## Usage

```bash
# Basic usage - same as multi-threaded version
python batch_spn_single.py sessions.yaml --vendor "cisco" -c "show version" -o inventory

# With debugging enabled
python batch_spn_single.py sessions.yaml --folder "core*" -c "show run" -o config --verbose

# Dry run to see what would execute
python batch_spn_single.py sessions.yaml --name "*switch*" -c "show interface status" -o interfaces --dry-run
```

## Command Line Options

All options are identical to the multi-threaded version except:
- **No `--max-workers`**: Not applicable for single-threaded execution
- **Added `--verbose`**: Shows real-time progress for each device
- **Added `--stop-on-error`**: Optionally halt execution on first failure

### Filtering Options
- `--folder PATTERN` - Filter by folder name (supports wildcards)
- `--name PATTERN` - Filter by device display name (supports wildcards)  
- `--vendor PATTERN` - Filter by vendor (supports wildcards)
- `--device-type TYPE` - Filter by device type

### Execution Options
- `-c, --commands` - Commands to execute (comma-separated)
- `-o, --output` - Output subdirectory name
- `--output-base` - Base output directory (default: capture)
- `--spn-script` - Path to spn.py script (default: spn.py)
- `--dry-run` - Show what would be executed without running
- `--verbose` - Show detailed progress information
- `--stop-on-error` - Stop execution on first device failure

### Output Options
- `--save-summary` - Save execution summary to JSON file
- `--list-devices` - Just list matching devices and exit

## Credential Management

Uses the same credential system as the multi-threaded version:

### Environment Variables (Recommended)
```bash
# Windows Command Prompt
set CRED_1_USER=admin
set CRED_1_PASS=password123

# Windows PowerShell
$env:CRED_1_USER='admin'
$env:CRED_1_PASS='password123'

# Linux/macOS
export CRED_1_USER='admin'
export CRED_1_PASS='password123'
```

### Multiple Credential Sets
```bash
# For credential ID "1"
CRED_1_USER=admin
CRED_1_PASS=admin_password

# For credential ID "2"  
CRED_2_USER=netadmin
CRED_2_PASS=network_password
```

## Example Session YAML

```yaml
- folder_name: "Core Network"
  sessions:
    - display_name: "core-sw-01"
      host: "192.168.1.10"
      port: "22"
      credsid: "1"
      Vendor: "Cisco"
      DeviceType: "network"
    
    - display_name: "core-sw-02"  
      host: "192.168.1.11"
      port: "22"
      credsid: "1"
      Vendor: "Cisco"
      DeviceType: "network"
```

## Output Structure

```
capture/
├── config/
│   ├── core-sw-01.txt     # Device output files
│   ├── core-sw-02.txt
│   ├── core-sw-01.log     # Error logs (if any)
│   └── execution_summary.json  # Optional summary
```

## Progress Monitoring

With `--verbose`, you'll see real-time progress:

```
Loading session files...
Loaded sessions.yaml

Matched 3 devices:
  - core-sw-01 (192.168.1.10) [Cisco] in 'Core Network'
  - core-sw-02 (192.168.1.11) [Cisco] in 'Core Network'  
  - core-sw-03 (192.168.1.12) [Cisco] in 'Core Network'

Executing commands on 3 devices (sequential)
Output directory: capture/config
Commands: terminal length 0,show running-config
------------------------------------------------------------

[1/3] Processing core-sw-01 (192.168.1.10)...
      Connected successfully
      Executing commands...
      Output saved to capture/config/core-sw-01.txt
      Completed in 8.2s
      
[2/3] Processing core-sw-02 (192.168.1.11)...
      Connected successfully  
      Executing commands...
      Output saved to capture/config/core-sw-02.txt
      Completed in 7.9s
      
[3/3] Processing core-sw-03 (192.168.1.12)...
      Connection failed: timeout
      Error logged to capture/config/core-sw-03.log
      Failed in 30.0s

============================================================
EXECUTION SUMMARY
============================================================
Total devices: 3
Successful: 2
Failed: 1  
Total time: 46.1s
Average time per device: 15.4s

Failed devices:
  - core-sw-03: Connection timeout
```

## Error Handling

The single-threaded version provides clearer error reporting:

- **Connection Errors**: Detailed timeout and authentication failures
- **Command Errors**: Shows exactly which command failed and why
- **Credential Errors**: Clear indication of missing or invalid credentials
- **File Errors**: Specific information about output directory issues

## Integration with spn.py

The single-threaded runner uses the same integration approach:
- Passes credentials via environment variables to each spn.py subprocess
- Uses `--no-screen` to suppress screen output during batch execution
- Lets spn.py handle all file output and carriage return cleanup
- Captures stderr for error logging

## Performance Considerations

**Single-threaded execution times:**
- Small batch (1-5 devices): Comparable to multi-threaded
- Medium batch (6-20 devices): 3-5x slower than multi-threaded
- Large batch (20+ devices): 5-10x slower than multi-threaded

## Performance Comparison - Large Scale (100 devices)

| Version | Execution Time | Success Rate | Avg per Device |
|---------|---------------|--------------|----------------|
| Multi-Process | 98.6s | 75% | 1.0s |
| Multi-Threaded | ~similar | ~similar | ~1.0s |
| Sequential | ~500-600s | ~similar | ~5-6s |

**Memory usage:**
- Minimal: Only one SSH connection at a time
- Suitable for resource-constrained environments
- No thread synchronization overhead

## Troubleshooting

### Common Issues

1. **Slow Execution**: Normal for single-threaded - consider multi-threaded version for large batches
2. **Credential Errors**: Verify environment variables are set correctly
3. **Permission Errors**: Ensure output directory is writable
4. **SSH Timeouts**: Individual devices may take longer due to sequential processing

### Debug Mode

Add `--verbose` to see detailed execution flow:
```bash
python batch_spn_single.py sessions.yaml --verbose -c "show version" -o test
```

### Testing

Always test with a small subset first:
```bash
# Test with just one device
python batch_spn_single.py sessions.yaml --name "core-sw-01" -c "show version" -o test --dry-run
```

## Migration from Multi-threaded

To switch from multi-threaded to single-threaded:

1. Replace `batch_spn.py` with `batch_spn_single.py` in your commands
2. Remove `--max-workers` parameter if used
3. Consider adding `--verbose` for progress monitoring
4. Adjust timeout expectations (will take longer overall)

The command syntax and all other options remain identical.