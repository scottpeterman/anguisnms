#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse
import traceback
from typing import List, Optional, Dict, Any, TextIO
from pathlib import Path
from datetime import datetime

from device_info import DeviceInfo, DeviceType
from ssh_client import SSHClient, SSHClientOptions
from device_fingerprint import DeviceFingerprint



class OutputManager:
    """Manages output to screen, file, or both with proper carriage return handling"""


    def __init__(self, output_to_screen=True, output_file=None, append_mode=False):
        self.output_to_screen = output_to_screen
        self.output_file = None
        self.append_mode = append_mode
        self.file_buffer = []  # Buffer for file content to clean up at the end

        if output_file:
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(output_file), exist_ok=True) if os.path.dirname(output_file) else None
                self.output_file_path = output_file
                mode = 'a' if append_mode else 'w'
                self.output_file = open(output_file, mode, encoding='utf-8')
            except Exception as e:
                print(f"Warning: Could not open output file {output_file}: {str(e)}")
                self.output_file = None
                self.output_file_path = None



    def write(self, text):
        """Write text to configured outputs"""
        # For screen output, keep original format (with \r for real-time display)
        if self.output_to_screen:
            print(text, end='')
            sys.stdout.flush()

        # For file output, clean the text before writing
        if self.output_file:
            try:
                # Clean the text before writing to file
                cleaned_text = self._clean_text_for_file(text)
                self.output_file.write(cleaned_text)
                self.output_file.flush()
            except Exception as e:
                print(f"Warning: Error writing to file: {str(e)}")

    def _clean_text_for_file(self, text):
        """Clean text for file output by removing carriage returns"""
        # Replace \r\n with \n, and standalone \r with \n
        cleaned = text.replace('\r\n', '\n').replace('\r', '\n')
        return cleaned


    def close(self):
        """Close file handle"""
        if self.output_file:
            try:
                self.output_file.close()
            except Exception as e:
                print(f"Warning: Error closing output file: {str(e)}")

class EnhancedSPN:
    VERSION = "1.1.0"
    COPYRIGHT = "Copyright (C) 2025 Enhanced SSHPassPython"

    def __init__(self):
        self.args = self.parse_arguments()

        # Resolve credentials (CLI args take precedence over env vars)
        self.credentials = self.resolve_credentials()

        # Parse host and port
        self.host, self.port = self.parse_host_port(self.credentials['host'])

        # Setup output management
        self.output_manager = self.setup_output_management()

        # Setup logging
        self.log_file = self.setup_logging()

    def parse_arguments(self):
        """Parse command line arguments with environment variable support"""
        parser = argparse.ArgumentParser(
            description=f"Enhanced SSHPassPython {self.VERSION}\n{self.COPYRIGHT}\n\n"
                        "Credentials can be provided via CLI arguments or environment variables:\n"
                        "  SSH_HOST, SSH_USER, SSH_PASSWORD, SSH_PORT\n"
                        "CLI arguments take precedence over environment variables.",
            formatter_class=argparse.RawTextHelpFormatter,
            add_help=False
        )

        parser.add_argument("--help", action="help", help="Show this help message and exit")

        # Connection arguments (support env vars as defaults)
        parser.add_argument("--host", "-h",
                            default=os.getenv('SSH_HOST', ''),
                            help="SSH Host (ip:port) [Env: SSH_HOST]")
        parser.add_argument("-u", "--user",
                            default=os.getenv('SSH_USER', ''),
                            help="SSH Username [Env: SSH_USER]")
        parser.add_argument("-p", "--password",
                            default=os.getenv('SSH_PASSWORD', ''),
                            help="SSH Password [Env: SSH_PASSWORD]")
        parser.add_argument("--port", type=int,
                            default=int(os.getenv('SSH_PORT', '22')),
                            help="SSH Port (default: 22) [Env: SSH_PORT]")

        # Command options
        parser.add_argument("-c", "--cmds", default="",
                            help="Commands to run, separated by comma")
        parser.add_argument("--cmd-file",
                            help="File containing commands (one per line)")

        # SSH options
        parser.add_argument("--invoke-shell", action="store_true",
                            help="Invoke shell mode (recommended for network devices)")
        parser.add_argument("--prompt", default="",
                            help="Expected prompt pattern (auto-detected if not provided)")
        parser.add_argument("--prompt-count", type=int, default=None,
                            help="Number of prompts to look for (default: auto-calculate based on command count)")
        parser.add_argument("-t", "--timeout", type=int, default=360,
                            help="Command timeout in seconds")
        parser.add_argument("--shell-timeout", type=int, default=10,
                            help="Shell session timeout in seconds")
        parser.add_argument("--expect-prompt-timeout", type=int, default=30000,
                            help="Expect prompt timeout in milliseconds")
        parser.add_argument("-i", "--inter-command-time", type=int, default=1,
                            help="Inter-command delay in seconds")

        # Output options
        parser.add_argument("--output-screen", action="store_true", default=True,
                            help="Output to screen (default: true)")
        parser.add_argument("--no-screen", action="store_true",
                            help="Disable screen output")
        parser.add_argument("-o", "--output-file", default="",
                            help="Save output to file")
        parser.add_argument("--append", action="store_true",
                            help="Append to output file instead of overwriting")

        # Logging and debugging
        parser.add_argument("--log-file", default="",
                            help="Log file path (default: ./logs/hostname.log)")
        parser.add_argument("-d", "--debug", action="store_true",
                            help="Enable debug output")
        parser.add_argument("-v", "--verbose", action="store_true",
                            help="Enable verbose output")

        # Device fingerprinting
        parser.add_argument("-f", "--fingerprint", action="store_true",
                            help="Fingerprint device before command execution")
        parser.add_argument("--fingerprint-output", default="",
                            help="Save fingerprint results to JSON file")
        parser.add_argument("--use-fingerprint-prompt", action="store_true",
                            help="Use detected prompt from fingerprinting")

        # Legacy support
        parser.add_argument("--legacy-mode", action="store_true",
                            help="Enable legacy device compatibility mode")
        parser.add_argument("--disable-paging-commands", default="",
                            help="Custom comma-separated list of paging disable commands")

        # Version
        parser.add_argument("--version", action="version",
                            version=f"Enhanced SSHPassPython {self.VERSION}")

        return parser.parse_args()

    def resolve_credentials(self):
        """Resolve credentials from CLI args and environment variables"""
        # CLI arguments take precedence over environment variables
        host = self.args.host or os.getenv('SSH_HOST', '')
        user = self.args.user or os.getenv('SSH_USER', '')
        password = self.args.password or os.getenv('SSH_PASSWORD', '')

        # Validate required credentials
        missing = []
        if not host:
            missing.append('host (--host or SSH_HOST)')
        if not user:
            missing.append('username (--user or SSH_USER)')
        if not password:
            missing.append('password (--password or SSH_PASSWORD)')

        if missing:
            print(f"Error: Missing required credentials: {', '.join(missing)}")
            sys.exit(1)

        return {
            'host': host,
            'user': user,
            'password': password
        }

    def parse_host_port(self, host_arg: str) -> tuple:
        """Parse host:port format"""
        if ":" in host_arg:
            host, port_str = host_arg.rsplit(":", 1)  # Use rsplit to handle IPv6
            try:
                port = int(port_str)
                return host, port
            except ValueError:
                print(f"Invalid port: {port_str}. Using port from --port argument.")
                return host_arg, self.args.port
        return host_arg, self.args.port

    def setup_output_management(self):
        """Setup output management based on arguments"""
        output_to_screen = self.args.output_screen and not self.args.no_screen
        output_file = self.args.output_file if self.args.output_file else None

        return OutputManager(
            output_to_screen=output_to_screen,
            output_file=output_file,
            append_mode=self.args.append
        )

    def setup_logging(self) -> str:
        """Setup logging path"""
        if self.args.log_file:
            return self.args.log_file
        else:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            os.makedirs(log_dir, exist_ok=True)
            return os.path.join(log_dir, f"{self.host}.log")

    def load_commands_from_file(self, cmd_file: str) -> List[str]:
        """Load commands from a file"""
        try:
            with open(cmd_file, 'r', encoding='utf-8') as f:
                commands = []
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):  # Skip empty lines and comments
                        commands.append(line)
                return commands
        except Exception as e:
            print(f"Error reading command file {cmd_file}: {str(e)}")
            sys.exit(1)

    def prepare_commands(self) -> List[str]:
        """Prepare and validate commands from all sources"""
        commands = []

        # Load from file if specified
        if self.args.cmd_file:
            commands.extend(self.load_commands_from_file(self.args.cmd_file))

        # Add from command line if specified
        if self.args.cmds:
            # Split by comma but preserve trailing empty entries for newlines
            cmd_parts = self.args.cmds.split(',')

            # Process commands with special handling for trailing empty commands
            processed_commands = []

            # First, filter out empty commands in the middle but keep track of trailing ones
            for i, cmd in enumerate(cmd_parts):
                cmd_stripped = cmd.strip()

                if cmd_stripped:
                    # Regular command
                    processed_commands.append(cmd_stripped)
                else:
                    # Empty command - check if it's trailing
                    remaining_parts = cmd_parts[i + 1:]
                    if all(not part.strip() for part in remaining_parts):
                        # All remaining parts are empty, so this and the rest are trailing newlines
                        trailing_newlines = len([p for p in cmd_parts[i:] if not p.strip()])
                        for _ in range(trailing_newlines):
                            processed_commands.append("\\n")  # Special marker for newline
                        break
                    # Otherwise skip this empty command (it's in the middle)

            commands.extend(processed_commands)

        if self.args.verbose and commands:
            actual_commands = [cmd for cmd in commands if cmd != "\\n"]
            newline_commands = len([cmd for cmd in commands if cmd == "\\n"])
            print(f"Prepared {len(actual_commands)} commands + {newline_commands} trailing newlines for execution")
            if self.args.debug:
                for i, cmd in enumerate(commands, 1):
                    display_cmd = "send newline (\\n)" if cmd == "\\n" else cmd
                    print(f"  [{i}] {display_cmd}")

        return commands

    def run_fingerprint(self) -> Optional[DeviceInfo]:
        """Run device fingerprinting using your existing methodology"""
        if self.args.verbose:
            print(f"Starting device fingerprinting on {self.host}:{self.port}...")

        def fingerprint_output_callback(output):
            if self.args.debug:
                self.output_manager.write(output)
        try:
            fingerprinter = DeviceFingerprint(
                host=self.host,
                port=self.port,
                username=self.credentials['user'],
                password=self.credentials['password'],
                output_callback=fingerprint_output_callback,
                debug=self.args.debug,
                verbose=self.args.verbose,
                textfsm_db_path="tfsm_templates.db"
            )
            device_info = fingerprinter.fingerprint()
            structured = fingerprinter.to_structured_output()
            print(json.dumps(structured, indent=2))
        except Exception as e:
            print(f"Error instantiating fingerprinter: {e}")
            traceback.print_exc()


        if device_info.success:
            if self.args.verbose:
                print(f"Device fingerprinted: {device_info.device_type.name}")
                if device_info.detected_prompt:
                    print(f"Detected prompt: '{device_info.detected_prompt}'")

            # Save fingerprint if requested
            if self.args.fingerprint_output:
                try:
                    with open(self.args.fingerprint_output, 'w') as f:
                        json.dump(device_info.to_dict(), f, indent=2)
                    print(f"Fingerprint saved to {self.args.fingerprint_output}")
                except Exception as e:
                    print(f"Error saving fingerprint: {str(e)}")
        else:
            print("Warning: Device fingerprinting failed, proceeding with default settings")

        return device_info

    def calculate_prompt_count(self, commands: List[str]) -> int:
        """Calculate intelligent prompt count based on your methodology"""
        # Count all commands including newline commands (they all expect prompts)
        total_commands = len(commands)

        # Your formula: number of commands + 1 not used
        # This accounts for:
        # - Initial prompt (device ready state)
        # - One prompt after each command execution (including newlines)
        calculated_count = total_commands

        if self.args.verbose:
            actual_commands = [cmd for cmd in commands if cmd != "\\n"]
            newline_commands = len([cmd for cmd in commands if cmd == "\\n"])
            print(
                f"Calculated prompt count: {calculated_count} ({len(actual_commands)} commands + {newline_commands} newlines + 1)")

        return calculated_count

    def create_ssh_options(self, device_info: Optional[DeviceInfo] = None,
                           commands: List[str] = None) -> SSHClientOptions:
        """Create SSH client options using your existing methodology with intelligent prompt count"""

        # Calculate intelligent prompt count unless manually overridden
        if self.args.prompt_count is not None:
            # Use manually specified prompt count
            prompt_count = self.args.prompt_count
            if self.args.verbose:
                print(f"Using manual prompt count: {prompt_count}")
        elif commands:
            # Use intelligent calculation based on your methodology
            prompt_count = self.calculate_prompt_count(commands)
        else:
            # Fallback for cases where commands aren't available yet
            prompt_count = 1

        # Start with basic options
        ssh_options = SSHClientOptions(
            host=self.host,
            port=self.port,
            username=self.credentials['user'],
            password=self.credentials['password'],
            invoke_shell=self.args.invoke_shell,
            prompt=self.args.prompt,
            prompt_count=prompt_count,  # Use calculated or manual count
            timeout=self.args.timeout,
            shell_timeout=self.args.shell_timeout,
            inter_command_time=self.args.inter_command_time,
            log_file=self.log_file,
            debug=self.args.debug,
            expect_prompt_timeout=self.args.expect_prompt_timeout
        )

        # Use fingerprinting results if available and requested
        if device_info and self.args.use_fingerprint_prompt:
            if device_info.detected_prompt:
                ssh_options.expect_prompt = device_info.detected_prompt
                if self.args.verbose:
                    print(f"Using detected prompt: '{device_info.detected_prompt}'")

        # Set up output callback to use our output manager
        ssh_options.output_callback = self.output_manager.write

        return ssh_options

    def execute_commands(self, commands: List[str], device_info: Optional[DeviceInfo] = None):
        """Execute commands using single-session shell mode with aggregate prompt counting"""
        if not commands:
            print("No commands to execute.")
            return

        if self.args.verbose:
            print(f"Executing {len(commands)} commands on {self.host}:{self.port}")

        ssh_options = self.create_ssh_options(device_info, commands)
        ssh_client = SSHClient(ssh_options)

        try:
            # Connect using your existing robust connection logic
            ssh_client.connect()

            # If in shell mode and no prompt specified, detect it automatically
            if self.args.invoke_shell and not self.args.prompt and not ssh_options.expect_prompt:
                if self.args.verbose:
                    print("No prompt specified, attempting automatic prompt detection...")

                try:
                    detected_prompt = ssh_client.find_prompt()
                    if detected_prompt:
                        ssh_client.set_expect_prompt(detected_prompt)
                        if self.args.verbose:
                            print(f"Auto-detected prompt: '{detected_prompt}'")
                    else:
                        if self.args.verbose:
                            print("Warning: Could not auto-detect prompt, using fallback timing")
                except Exception as e:
                    if self.args.debug:
                        print(f"Prompt detection failed: {str(e)}")
                    if self.args.verbose:
                        print("Warning: Prompt detection failed, using fallback timing")

            # Add disable paging commands if we have device info
            if device_info and device_info.disable_paging_command and not self.args.legacy_mode:
                disable_cmd = device_info.disable_paging_command
                if self.args.verbose:
                    print(f"Disabling paging with: {disable_cmd}")
                # Insert at the beginning of command list
                commands.insert(0, disable_cmd)
                # Recalculate SSH options with updated command count
                ssh_options = self.create_ssh_options(device_info, commands)
                ssh_client._options = ssh_options
            elif self.args.disable_paging_commands:
                # Use custom disable paging commands
                paging_cmds = [cmd.strip() for cmd in self.args.disable_paging_commands.split(',') if cmd.strip()]
                if self.args.verbose:
                    print(f"Using custom paging commands: {paging_cmds}")
                # Insert at the beginning
                commands = paging_cmds + commands
                # Recalculate SSH options
                ssh_options = self.create_ssh_options(device_info, commands)
                ssh_client._options = ssh_options

            # CRITICAL: Execute all commands in ONE session when using shell mode
            if self.args.invoke_shell:
                if self.args.verbose:
                    print(f"Shell mode: Executing all {len(commands)} commands in single session")
                    if self.args.debug:
                        for i, cmd in enumerate(commands, 1):
                            display_cmd = "send newline" if cmd == "\\n" else cmd
                            print(f"  [{i}] {display_cmd}")

                # Convert command list to comma-separated string (your original format)
                # Handle newline commands specially
                command_parts = []
                for cmd in commands:
                    if cmd == "\\n":
                        command_parts.append("")  # Empty string creates trailing comma = newline
                    else:
                        command_parts.append(cmd)

                # Join with commas - empty parts will create the trailing commas you need
                combined_commands = ",".join(command_parts)

                if self.args.verbose:
                    print(f"Combined command string: '{combined_commands}'")

                # Execute as single session with aggregate prompt counting
                result = ssh_client.execute_command(combined_commands)

            else:
                # Non-shell mode: Execute commands individually
                if self.args.verbose:
                    print(f"Direct mode: Executing {len(commands)} commands individually")

                for i, cmd in enumerate(commands, 1):
                    if cmd == "\\n":
                        continue  # Skip newlines in direct mode

                    cmd = cmd.strip()
                    if not cmd:
                        continue

                    if self.args.verbose:
                        print(f"[{i}/{len(commands)}] Executing: {cmd}")

                    result = ssh_client.execute_command(cmd)

            ssh_client.disconnect()

        except Exception as e:
            print(f"Error during command execution: {str(e)}")
            if self.args.debug:
                traceback.print_exc()
            sys.exit(1)

    def run(self):
        """Main execution logic leveraging your existing methodology"""
        print(f"Enhanced SSHPassPython {self.VERSION}")
        print(f"Connecting to {self.host}:{self.port} as {self.credentials['user']}...")

        device_info = None

        # Run fingerprinting if requested
        if self.args.fingerprint:
            device_info = self.run_fingerprint()

        # Prepare commands early so we can calculate prompt count
        commands = self.prepare_commands()

        # Execute commands if any provided
        if commands:
            self.execute_commands(commands, device_info)
        elif not self.args.fingerprint:
            print("No commands provided. Use -c, --cmd-file, or -f for fingerprinting.")

        # Close output manager
        self.output_manager.close()

        if self.args.verbose:
            print("Execution completed.")


def main():
    """Entry point"""
    try:
        spn = EnhancedSPN()
        spn.run()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()