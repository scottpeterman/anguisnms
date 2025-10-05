#!/usr/bin/env python3
"""
Batch SSH Collection Wrapper for Enhanced SSHPassPython
Filters devices from YAML session files and executes spn.py commands in batch
"""

import os
import sys
import yaml
import argparse
import subprocess
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import re
import concurrent.futures
from threading import Lock

# Optional: Hardcoded credential mapping (fallback if env vars not found)
# For production, leave this empty and use environment variables only
CREDENTIAL_MAP = {
    # '1': {'user': 'admin', 'password': 'your_password_here'},
    # '2': {'user': 'netadmin', 'password': 'another_password'},
}


class DeviceFilter:
    """Handles device filtering based on query criteria"""

    def __init__(self, sessions_data: List[Dict]):
        self.sessions_data = sessions_data

    def filter_devices(self, folder_pattern: str = None, name_pattern: str = None,
                       vendor_pattern: str = None, device_type: str = None) -> List[Dict]:
        """Filter devices based on multiple criteria"""
        matched_devices = []

        for folder_group in self.sessions_data:
            folder_name = folder_group.get('folder_name', '')

            # Filter by folder pattern
            if folder_pattern and not self._match_pattern(folder_name, folder_pattern):
                continue

            for device in folder_group.get('sessions', []):
                # Filter by display name pattern
                if name_pattern and not self._match_pattern(device.get('display_name', ''), name_pattern):
                    continue

                # Filter by vendor pattern
                if vendor_pattern and not self._match_pattern(device.get('Vendor', ''), vendor_pattern):
                    continue

                # Filter by device type
                if device_type and device.get('DeviceType', '').lower() != device_type.lower():
                    continue

                # Add folder context to device info
                device_with_context = device.copy()
                device_with_context['folder_name'] = folder_name
                matched_devices.append(device_with_context)

        return matched_devices

    def _match_pattern(self, text: str, pattern: str) -> bool:
        """Match text against pattern (supports wildcards and regex)"""
        if not pattern:
            return True

        text = text.lower()
        pattern = pattern.lower()

        # Simple wildcard support
        if '*' in pattern:
            pattern = pattern.replace('*', '.*')
            return re.match(pattern, text) is not None

        # Substring match
        return pattern in text


class CredentialManager:
    """Handles credential lookup by credential ID"""

    def __init__(self):
        pass

    def get_credentials(self, cred_id: str) -> Dict[str, str]:
        """Get credentials for a given credential ID"""
        # First try environment variables (preferred method)
        env_user = os.getenv(f'CRED_{cred_id}_USER')
        env_pass = os.getenv(f'CRED_{cred_id}_PASS')

        if env_user and env_pass:
            return {'user': env_user, 'password': env_pass}

        # Fallback to hardcoded mapping
        if cred_id in CREDENTIAL_MAP:
            return CREDENTIAL_MAP[cred_id]

        # No credentials found
        raise ValueError(f"No credentials found for cred_id '{cred_id}'. "
                         f"Set environment variables CRED_{cred_id}_USER and CRED_{cred_id}_PASS")

    def validate_credentials(self, devices: List[Dict]) -> bool:
        """Validate that credentials are available for all devices"""
        missing_creds = set()

        for device in devices:
            cred_id = device.get('credsid', '')
            if not cred_id:
                missing_creds.add(f"Device '{device.get('display_name', 'unknown')}' has no credsid")
                continue

            try:
                self.get_credentials(cred_id)
            except ValueError as e:
                missing_creds.add(str(e))

        if missing_creds:
            print("ERROR: Missing credentials:")
            for error in sorted(missing_creds):
                print(f"  - {error}")
            print(f"\nFor Windows, set environment variables like:")
            print(f"  set CRED_1_USER=admin")
            print(f"  set CRED_1_PASS=your_password")
            print(f"\nOr use PowerShell:")
            print(f"  $env:CRED_1_USER='admin'")
            print(f"  $env:CRED_1_PASS='your_password'")
            return False

        return True


class BatchExecutor:
    """Executes spn.py commands in batch - lets spn.py handle all file output"""

    def __init__(self, spn_script_path: str, base_output_dir: str = "capture"):
        self.spn_script_path = spn_script_path
        self.base_output_dir = base_output_dir
        self.results_lock = Lock()
        self.execution_results = []
        self.credential_manager = CredentialManager()

    def execute_batch(self, devices: List[Dict], commands: str, output_subdir: str,
                      max_workers: int = 5, dry_run: bool = False) -> Dict[str, Any]:
        """Execute commands against all devices in parallel"""

        # Validate credentials first
        if not self.credential_manager.validate_credentials(devices):
            return {"error": "Credential validation failed"}

        if dry_run:
            print(f"DRY RUN: Would execute on {len(devices)} devices")
            for device in devices:
                cred_id = device.get('credsid', 'N/A')
                print(
                    f"  - {device['display_name']} ({device['host']}) [cred_id: {cred_id}] -> {output_subdir}/{device['display_name']}.txt")
            return {"dry_run": True, "device_count": len(devices)}

        # Create output directory (spn.py will create the files)
        output_dir = Path(self.base_output_dir) / output_subdir
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Executing commands on {len(devices)} devices (max {max_workers} parallel)")
        print(f"Output directory: {output_dir}")
        print(f"Commands: {commands}")
        print("-" * 60)

        start_time = datetime.now()

        # Execute in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_device = {
                executor.submit(self._execute_single_device, device, commands, output_dir): device
                for device in devices
            }

            for future in concurrent.futures.as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    result = future.result()
                    with self.results_lock:
                        self.execution_results.append(result)

                    status = "SUCCESS" if result['success'] else "FAILED"
                    print(f"[{status}] {device['display_name']} - {result.get('message', '')}")

                except Exception as exc:
                    error_result = {
                        'device': device['display_name'],
                        'host': device['host'],
                        'success': False,
                        'message': f'Exception: {exc}',
                        'execution_time': 0
                    }
                    with self.results_lock:
                        self.execution_results.append(error_result)
                    print(f"[ERROR] {device['display_name']} - Exception: {exc}")

        end_time = datetime.now()
        execution_summary = self._generate_summary(start_time, end_time)

        return execution_summary

    def _execute_single_device(self, device: Dict, commands: str, output_dir: Path) -> Dict[str, Any]:
        """Execute spn.py command against a single device - let spn.py handle file output"""
        device_name = device['display_name']
        host = device['host']
        port = device.get('port', '22')
        cred_id = device.get('credsid', '')

        try:
            # Get credentials for this device
            credentials = self.credential_manager.get_credentials(cred_id)
        except ValueError as e:
            return {
                'device': device_name,
                'host': host,
                'success': False,
                'message': f'Credential error: {str(e)}',
                'execution_time': 0
            }

        # Output file path - let spn.py create and manage this file
        output_file = output_dir / f"{device_name}.txt"

        # Build spn.py command - pass credentials via environment variables
        cmd_args = [
            sys.executable, self.spn_script_path,
            '--host', f"{host}:{port}",
            '-c', commands,
            '--invoke-shell',
            '--output-file', str(output_file),  # Let spn.py handle the file
            '--no-screen',  # Don't output to screen during batch
            '--verbose'
        ]

        # Set up environment variables for spn.py subprocess
        env = os.environ.copy()
        env['SSH_HOST'] = f"{host}:{port}"
        env['SSH_USER'] = credentials['user']
        env['SSH_PASSWORD'] = credentials['password']

        start_time = datetime.now()

        try:
            # Execute spn.py - let it handle all file output and cleanup
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout per device
                env=env
            )

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            success = result.returncode == 0

            # Only save stderr to log file if there were errors
            if result.stderr:
                log_file = output_dir / f"{device_name}.log"
                with open(log_file, 'w') as f:
                    f.write(f"Command: {' '.join(cmd_args)}\n")
                    f.write(f"Device: {device_name} ({host})\n")
                    f.write(f"Credentials ID: {cred_id}\n")
                    f.write(f"Return code: {result.returncode}\n")
                    f.write(f"STDERR:\n{result.stderr}\n")
                    if result.stdout:
                        f.write(f"STDOUT:\n{result.stdout}\n")

            return {
                'device': device_name,
                'host': host,
                'cred_id': cred_id,
                'success': success,
                'return_code': result.returncode,
                'execution_time': execution_time,
                'output_file': str(output_file),
                'message': 'Completed successfully' if success else f'Exit code: {result.returncode}'
            }

        except subprocess.TimeoutExpired:
            return {
                'device': device_name,
                'host': host,
                'cred_id': cred_id,
                'success': False,
                'message': 'Command timed out (600s)',
                'execution_time': 600
            }
        except Exception as e:
            return {
                'device': device_name,
                'host': host,
                'cred_id': cred_id,
                'success': False,
                'message': f'Execution error: {str(e)}',
                'execution_time': 0
            }

    def _generate_summary(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate execution summary"""
        total_time = (end_time - start_time).total_seconds()
        successful = len([r for r in self.execution_results if r['success']])
        failed = len(self.execution_results) - successful

        summary = {
            'total_devices': len(self.execution_results),
            'successful': successful,
            'failed': failed,
            'total_execution_time': total_time,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'results': self.execution_results
        }

        print(f"\n{'=' * 60}")
        print(f"EXECUTION SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total devices: {summary['total_devices']}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total time: {total_time:.1f}s")
        print(f"Average time per device: {total_time / len(self.execution_results):.1f}s")

        if failed > 0:
            print(f"\nFailed devices:")
            for result in self.execution_results:
                if not result['success']:
                    print(f"  - {result['device']}: {result['message']}")

        return summary


def load_sessions(yaml_files: List[str]) -> List[Dict]:
    """Load session data from YAML files"""
    all_sessions = []

    for yaml_file in yaml_files:
        try:
            with open(yaml_file, 'r') as f:
                sessions = yaml.safe_load(f)
                if isinstance(sessions, list):
                    all_sessions.extend(sessions)
                else:
                    all_sessions.append(sessions)
            print(f"Loaded {yaml_file}")
        except Exception as e:
            print(f"Error loading {yaml_file}: {e}")
            sys.exit(1)

    return all_sessions


def main():
    parser = argparse.ArgumentParser(
        description="Batch SSH automation wrapper for Enhanced SSHPassPython",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get version info from all Palo Alto devices
  python batch_spn.py sessions.yaml --vendor "palo*" -c "show system info" -o version

  # Backup configs from all switches in ATS folder
  python batch_spn.py sessions.yaml --folder "ATS*" --name "*sw*" -c "show running-config" -o config

  # Show all Aruba devices (dry run)
  python batch_spn.py sessions.yaml --vendor "aruba" --dry-run

  # Run on specific device types with custom output
  python batch_spn.py sessions.yaml --device-type network --folder "*retail*" -c "show version" -o inventory
        """
    )

    # Input files
    parser.add_argument('yaml_files', nargs='+', help='YAML session files to process')

    # Filter options
    parser.add_argument('--folder', help='Filter by folder name (supports wildcards)')
    parser.add_argument('--name', help='Filter by device display name (supports wildcards)')
    parser.add_argument('--vendor', help='Filter by vendor (supports wildcards)')
    parser.add_argument('--device-type', help='Filter by device type')

    # Execution options
    parser.add_argument('-c', '--commands', required=True, help='Commands to execute (same format as spn.py)')
    parser.add_argument('-o', '--output', required=True, help='Output subdirectory (e.g., "config", "version")')
    parser.add_argument('--output-base', default='capture', help='Base output directory (default: capture)')

    # Execution control
    parser.add_argument('--max-workers', type=int, default=5, help='Maximum parallel executions (default: 5)')
    parser.add_argument('--spn-script', default='spn.py', help='Path to spn.py script (default: spn.py)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be executed without running')

    # Output control
    parser.add_argument('--save-summary', help='Save execution summary to JSON file')
    parser.add_argument('--list-devices', action='store_true', help='Just list matching devices and exit')

    args = parser.parse_args()

    # Load session data
    print("Loading session files...")
    sessions = load_sessions(args.yaml_files)

    # Filter devices
    device_filter = DeviceFilter(sessions)
    matched_devices = device_filter.filter_devices(
        folder_pattern=args.folder,
        name_pattern=args.name,
        vendor_pattern=args.vendor,
        device_type=args.device_type
    )

    if not matched_devices:
        print("No devices matched the specified criteria.")
        sys.exit(1)

    print(f"\nMatched {len(matched_devices)} devices:")
    for device in matched_devices:
        vendor = device.get('Vendor', 'Unknown')
        folder = device.get('folder_name', 'Unknown')
        print(f"  - {device['display_name']} ({device['host']}) [{vendor}] in '{folder}'")

    if args.list_devices:
        sys.exit(0)

    # Execute batch commands
    executor = BatchExecutor(args.spn_script, args.output_base)
    summary = executor.execute_batch(
        devices=matched_devices,
        commands=args.commands,
        output_subdir=args.output,
        max_workers=args.max_workers,
        dry_run=args.dry_run
    )

    # Save summary if requested
    if args.save_summary and not args.dry_run:
        with open(args.save_summary, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\nExecution summary saved to {args.save_summary}")


if __name__ == "__main__":
    main()