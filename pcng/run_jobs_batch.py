#!/usr/bin/env python3
"""
Network Job Batch Runner CLI
Sequential execution of multiple network automation job configurations
"""

import sys
import os
import json
import yaml
import subprocess
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class VendorCommandManager:
    """Manages vendor-specific command templates and prefixes"""

    def __init__(self):
        self.vendor_configs = {
            'cisco': {
                'paging_disable': 'terminal length 0',
                'additional_args': '--invoke-shell',
                'description': 'Cisco IOS/IOS-XE devices'
            },
            'arista': {
                'paging_disable': 'terminal length 0',
                'additional_args': '--invoke-shell',
                'description': 'Arista EOS devices'
            },
            'paloalto': {
                'paging_disable': 'set cli pager off',
                'additional_args': '--prompt-count 3 --expect-prompt-timeout 15000 --invoke-shell',
                'description': 'Palo Alto firewalls'
            },
            'cloudgenix': {
                'paging_disable': 'set paging off',
                'additional_args': '--prompt-count 3 --expect-prompt-timeout 15000 --invoke-shell',
                'description': 'CloudGenix SD-WAN devices'
            },
            'juniper': {
                'paging_disable': 'set cli screen-length 0',
                'additional_args': '--invoke-shell',
                'description': 'Juniper JunOS devices'
            },
            'fortinet': {
                'paging_disable': 'config system console\nset output standard\nend',
                'additional_args': '--invoke-shell',
                'description': 'Fortinet FortiGate firewalls'
            },
            'generic': {
                'paging_disable': '',
                'additional_args': '',
                'description': 'Generic/Unknown devices (no paging disable)'
            }
        }

    def get_vendor_config(self, vendor: str) -> Dict[str, str]:
        """Get configuration for a specific vendor"""
        return self.vendor_configs.get(vendor.lower(), self.vendor_configs['generic'])

    def build_command_with_paging(self, vendor: str, commands: str) -> str:
        """Build command string with vendor-specific paging disable prefix"""
        config = self.get_vendor_config(vendor)
        paging_cmd = config['paging_disable']

        if paging_cmd and commands:
            return f"{paging_cmd},{commands}"
        elif paging_cmd:
            return paging_cmd
        else:
            return commands

    def get_additional_args(self, vendor: str) -> str:
        """Get additional arguments for vendor-specific execution"""
        config = self.get_vendor_config(vendor)
        return config['additional_args']


class JobExecutor:
    """Executes individual network automation jobs"""

    def __init__(self, vendor_manager: VendorCommandManager, verbose: bool = False):
        self.vendor_manager = vendor_manager
        self.verbose = verbose

    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def get_credential_env_vars(self, job_config: Dict[str, Any]) -> Dict[str, str]:
        """Get environment variables for credentials from job config"""
        env_vars = {}

        credentials = job_config.get('credentials', {})
        username = credentials.get('username', '')

        # For batch operations, we typically use CRED_* format
        if username:
            # Set multiple credential IDs as fallback
            for cred_id in range(1, 11):
                env_vars.update({
                    f'CRED_{cred_id}_USER': username,
                })

            self.log(f"Configured credentials for user: {username}")
            self.log("Note: Passwords must be set via environment variables")

        return env_vars

    def execute_job(self, job_config: Dict[str, Any], job_name: str) -> Dict[str, Any]:
        """Execute a single job configuration"""
        start_time = time.time()

        try:
            self.log(f"Starting job: {job_name}")

            # Validate job configuration
            required_fields = ['session_file', 'commands', 'execution']
            for field in required_fields:
                if field not in job_config:
                    raise ValueError(f"Missing required field in job config: {field}")

            session_file = job_config['session_file']
            if not os.path.exists(session_file):
                raise FileNotFoundError(f"Session file not found: {session_file}")

            # Extract configuration
            vendor_info = job_config.get('vendor', {})
            vendor = vendor_info.get('selected', 'generic').lower()
            auto_paging = vendor_info.get('auto_paging', True)

            filters = job_config.get('filters', {})
            commands_info = job_config.get('commands', {})
            execution_info = job_config.get('execution', {})

            # Build command with vendor-specific paging
            base_commands = commands_info.get('command_text', '')
            if auto_paging:
                final_commands = self.vendor_manager.build_command_with_paging(vendor, base_commands)
            else:
                final_commands = base_commands

            output_dir = commands_info.get('output_directory', 'output')

            # Determine batch script
            batch_script_text = execution_info.get('batch_script', 'batch_spn.py (Multi-threaded)')
            batch_script_map = {
                "batch_spn.py (Multi-threaded)": "batch_spn.py",
                "batch_spn_concurrent.py (Multi-process)": "batch_spn_concurrent.py"
            }
            batch_script = batch_script_map.get(batch_script_text, "batch_spn.py")

            if not os.path.exists(batch_script):
                raise FileNotFoundError(f"Batch script not found: {batch_script}")

            # Build command arguments
            cmd_args = [sys.executable, batch_script, session_file]

            # Add filters
            filter_mapping = [
                ('--folder', filters.get('folder')),
                ('--name', filters.get('name')),
                ('--vendor', filters.get('vendor')),
                ('--device-type', filters.get('device_type'))
            ]

            for filter_name, filter_value in filter_mapping:
                if filter_value and filter_value.strip():
                    cmd_args.extend([filter_name, filter_value.strip()])
                    self.log(f"Applied filter: {filter_name} = '{filter_value.strip()}'")

            # Add execution parameters
            cmd_args.extend(['-c', final_commands])
            cmd_args.extend(['-o', output_dir])

            # Add execution settings
            max_workers = execution_info.get('max_workers', 5)
            verbose = execution_info.get('verbose', False)
            dry_run = execution_info.get('dry_run', False)

            # Script-specific argument handling
            script_name = os.path.basename(batch_script)
            if script_name == 'batch_spn_concurrent.py':
                cmd_args.extend(['--max-processes', str(max_workers)])
                if verbose:
                    cmd_args.append('--verbose')
            elif script_name == 'batch_spn.py':
                cmd_args.extend(['--max-workers', str(max_workers)])
                # batch_spn.py doesn't support --verbose

            if dry_run:
                cmd_args.append('--dry-run')

            # Set up environment
            env = os.environ.copy()
            credential_vars = self.get_credential_env_vars(job_config)
            env.update(credential_vars)

            # Log execution details
            command_str = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd_args)
            self.log(f"Executing: {command_str}")
            self.log(f"Final commands: {final_commands}")
            self.log(f"Output directory: capture/{output_dir}")

            # Execute the job
            process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )

            # Monitor output if verbose
            if self.verbose:
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        print(output.strip())

            # Wait for completion
            stdout, stderr = process.communicate()

            execution_time = time.time() - start_time

            # Prepare result
            result = {
                'job_name': job_name,
                'success': process.returncode == 0,
                'return_code': process.returncode,
                'execution_time': execution_time,
                'output_directory': f"capture/{output_dir}",
                'commands': final_commands,
                'stdout': stdout,
                'stderr': stderr
            }

            if result['success']:
                self.log(f"Job completed successfully in {execution_time:.1f}s")
            else:
                self.log(f"Job failed after {execution_time:.1f}s", "ERROR")
                if stderr:
                    self.log(f"Error output: {stderr}", "ERROR")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            self.log(f"Job failed with exception: {error_msg}", "ERROR")

            return {
                'job_name': job_name,
                'success': False,
                'return_code': -1,
                'execution_time': execution_time,
                'error': error_msg,
                'stdout': '',
                'stderr': ''
            }


class JobBatchRunner:
    """Manages batch execution of multiple network automation jobs"""

    def __init__(self, verbose: bool = False):
        self.vendor_manager = VendorCommandManager()
        self.job_executor = JobExecutor(self.vendor_manager, verbose)
        self.verbose = verbose

    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def load_job_list(self, job_list_file: str) -> List[str]:
        """Load list of job configuration files"""
        job_files = []

        try:
            with open(job_list_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue

                    # Handle absolute and relative paths
                    job_file = line
                    if not os.path.isabs(job_file):
                        # Make relative to the job list file's directory
                        job_list_dir = os.path.dirname(os.path.abspath(job_list_file))
                        job_file = os.path.join(job_list_dir, job_file)

                    if not os.path.exists(job_file):
                        self.log(f"Warning: Job file not found (line {line_num}): {job_file}", "WARN")
                        continue

                    job_files.append(job_file)

            self.log(f"Loaded {len(job_files)} job configuration files")
            return job_files

        except Exception as e:
            raise RuntimeError(f"Failed to load job list file: {str(e)}")

    def load_job_config(self, job_file: str) -> Dict[str, Any]:
        """Load a job configuration file"""
        try:
            with open(job_file, 'r', encoding='utf-8') as f:
                job_config = json.load(f)

            # Validate basic structure
            if not isinstance(job_config, dict):
                raise ValueError("Job configuration must be a dictionary")

            return job_config

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in job file {job_file}: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to load job file {job_file}: {str(e)}")

    def run_batch(self, job_list_file: str, continue_on_error: bool = True,
                  max_retries: int = 0) -> Dict[str, Any]:
        """Run a batch of jobs from a job list file"""

        self.log("=" * 60)
        self.log("NETWORK JOB BATCH RUNNER STARTING")
        self.log("=" * 60)

        start_time = time.time()

        # Load job list
        try:
            job_files = self.load_job_list(job_list_file)
        except Exception as e:
            self.log(f"Failed to load job list: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

        if not job_files:
            self.log("No valid job files found in job list", "ERROR")
            return {'success': False, 'error': 'No valid job files found'}

        # Execute jobs
        results = []
        successful_jobs = 0
        failed_jobs = 0

        for i, job_file in enumerate(job_files, 1):
            job_name = os.path.basename(job_file)

            self.log("-" * 40)
            self.log(f"JOB {i}/{len(job_files)}: {job_name}")
            self.log("-" * 40)

            try:
                # Load job configuration
                job_config = self.load_job_config(job_file)

                # Execute job with retries
                attempts = 0
                job_result = None

                while attempts <= max_retries:
                    if attempts > 0:
                        self.log(f"Retry attempt {attempts}/{max_retries} for {job_name}")

                    job_result = self.job_executor.execute_job(job_config, job_name)

                    if job_result['success']:
                        break

                    attempts += 1
                    if attempts <= max_retries:
                        time.sleep(2)  # Brief pause before retry

                results.append(job_result)

                if job_result['success']:
                    successful_jobs += 1
                    self.log(f"✓ Job {i}/{len(job_files)} completed successfully")
                else:
                    failed_jobs += 1
                    self.log(f"✗ Job {i}/{len(job_files)} failed", "ERROR")

                    if not continue_on_error:
                        self.log("Stopping batch execution due to job failure", "ERROR")
                        break

            except Exception as e:
                failed_jobs += 1
                error_result = {
                    'job_name': job_name,
                    'success': False,
                    'return_code': -1,
                    'execution_time': 0,
                    'error': f"Failed to load/execute job: {str(e)}"
                }
                results.append(error_result)

                self.log(f"✗ Job {i}/{len(job_files)} failed to load: {str(e)}", "ERROR")

                if not continue_on_error:
                    self.log("Stopping batch execution due to job failure", "ERROR")
                    break

        # Generate summary
        total_time = time.time() - start_time

        self.log("=" * 60)
        self.log("BATCH EXECUTION SUMMARY")
        self.log("=" * 60)
        self.log(f"Total jobs: {len(job_files)}")
        self.log(f"Successful: {successful_jobs}")
        self.log(f"Failed: {failed_jobs}")
        self.log(f"Total execution time: {total_time:.1f}s")
        self.log(f"Average time per job: {total_time / len(results):.1f}s" if results else "N/A")

        # Detailed results
        if results:
            self.log("\nDetailed Results:")
            for result in results:
                status = "SUCCESS" if result['success'] else "FAILED"
                time_str = f"{result['execution_time']:.1f}s"
                self.log(f"  {result['job_name']}: {status} ({time_str})")

                if not result['success'] and 'error' in result:
                    self.log(f"    Error: {result['error']}")

        batch_result = {
            'success': failed_jobs == 0,
            'total_jobs': len(job_files),
            'successful_jobs': successful_jobs,
            'failed_jobs': failed_jobs,
            'total_time': total_time,
            'job_results': results
        }

        return batch_result


def create_sample_job_list():
    """Create a sample job list file for demonstration"""
    sample_content = """# Network Job Batch List
# Lines starting with # are comments
# List one job configuration file per line

# Configuration backup jobs
job1_cisco_config_backup.json
job2_arista_version_check.json

# Inventory collection jobs  
job3_interface_status.json
job4_system_info.json

# You can use absolute paths too:
# /path/to/special_job.json
"""

    with open('sample_job_list.txt', 'w') as f:
        f.write(sample_content)

    print("Created sample_job_list.txt")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Network Job Batch Runner - Execute multiple network automation jobs sequentially",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s jobs.txt                    # Run jobs listed in jobs.txt
  %(prog)s jobs.txt --verbose          # Run with detailed output
  %(prog)s jobs.txt --stop-on-error    # Stop if any job fails
  %(prog)s jobs.txt --retries 2        # Retry failed jobs up to 2 times
  %(prog)s --create-sample             # Create sample job list file

Job List File Format:
  - One job configuration file per line
  - Lines starting with # are comments
  - Blank lines are ignored
  - Supports both relative and absolute paths
        """
    )

    parser.add_argument(
        'job_list_file',
        nargs='?',
        help='File containing list of job configuration files to execute'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output (show job execution details)'
    )

    parser.add_argument(
        '--stop-on-error',
        action='store_true',
        help='Stop batch execution if any job fails (default: continue with remaining jobs)'
    )

    parser.add_argument(
        '--retries', '-r',
        type=int,
        default=0,
        help='Number of retry attempts for failed jobs (default: 0)'
    )

    parser.add_argument(
        '--create-sample',
        action='store_true',
        help='Create a sample job list file and exit'
    )

    args = parser.parse_args()

    # Handle sample creation
    if args.create_sample:
        create_sample_job_list()
        return 0

    # Validate arguments
    if not args.job_list_file:
        parser.error("job_list_file is required (or use --create-sample)")

    if not os.path.exists(args.job_list_file):
        print(f"Error: Job list file not found: {args.job_list_file}")
        return 1

    try:
        # Create and run batch runner
        batch_runner = JobBatchRunner(verbose=args.verbose)

        result = batch_runner.run_batch(
            job_list_file=args.job_list_file,
            continue_on_error=not args.stop_on_error,
            max_retries=args.retries
        )

        # Exit with appropriate code
        return 0 if result['success'] else 1

    except KeyboardInterrupt:
        print("\nBatch execution interrupted by user")
        return 1
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())