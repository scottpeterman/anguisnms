# Enhanced ssh_client.py additions for legacy support
import sys
import time
import re
import logging
import os
import paramiko
from io import StringIO
from datetime import datetime

from ssh_router import SimpleSSHRouter


def filter_ansi_sequences(text):
    """
    Aggressively filter ANSI escape sequences and control characters

    Args:
        text (str): Input text with potential ANSI sequences

    Returns:
        str: Cleaned text
    """
    if not text:
        return text

    # Single comprehensive regex to remove all ANSI sequences and control chars
    # This catches \u001b[1;24r, \u001b[24;1H, \u001b[2K, \u001b[?25h, etc.
    ansi_pattern = r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b[()][AB012]|\x07|[\x00-\x08\x0B\x0C\x0E-\x1F]'
    return re.sub(ansi_pattern, '', text)


class SSHClientOptions:
    def __init__(self, host, username, password, port=22, invoke_shell=False,
                 expect_prompt=None, prompt=None, prompt_count=1, timeout=360,
                 shell_timeout=5, inter_command_time=1, log_file=None, debug=False,
                 expect_prompt_timeout=30000, legacy_mode=False):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.invoke_shell = invoke_shell
        self.expect_prompt = expect_prompt
        self.prompt = prompt
        self.prompt_count = prompt_count
        self.timeout = timeout
        self.shell_timeout = shell_timeout
        self.inter_command_time = inter_command_time
        self.log_file = log_file
        self.debug = debug
        self.expect_prompt_timeout = expect_prompt_timeout

        # New legacy support options
        self.legacy_mode = legacy_mode
        self.legacy_algorithms = True  # Enable by default for compatibility
        self.legacy_auth_methods = True
        self.legacy_prompt_detection = False  # Use original simple prompt detection if True
        self.disable_host_key_checking = True  # Common for lab/legacy equipment

        # Legacy-specific timing adjustments
        if legacy_mode:
            self.shell_timeout = max(self.shell_timeout, 3)  # Minimum 3s for legacy
            self.inter_command_time = max(self.inter_command_time, 0.5)  # Slower devices
            self.expect_prompt_timeout = max(self.expect_prompt_timeout, 10000)  # 10s minimum
            self.legacy_prompt_detection = True

        # Default callbacks
        self.output_callback = print
        self.error_callback = lambda msg: print("ERROR: {}".format(msg), file=sys.stderr)

        self.routing_enabled = os.getenv('SSH_USE_ROUTING', 'false').lower() == 'true'
        self.proxy_host = os.getenv('SSH_PROXY_HOST')
        self.proxy_port = int(os.getenv('SSH_PROXY_PORT', '22'))
        self.proxy_username = os.getenv('SSH_PROXY_USER')
        self.proxy_password = os.getenv('SSH_PROXY_PASS')
        self.proxy_key_path = os.getenv('SSH_PROXY_KEY')

        # Parse routing rules from environment
        self.routing_rules = self._parse_routing_rules()

        if self.routing_enabled and self.debug:
            print(f"SSH Routing enabled with {len(self.routing_rules)} rules")

    def _parse_routing_rules(self):
        """Parse routing rules from environment variable"""
        rules_json = os.getenv('SSH_ROUTING_RULES')
        if not rules_json:
            return []

        try:
            import json
            return json.loads(rules_json)
        except Exception as e:
            print(f"Error parsing routing rules: {e}")
            return []


class LegacySSHClientEnhancements:
    """Enhancements to SSHClient for legacy device support"""

    @staticmethod
    def configure_legacy_algorithms(ssh_client):
        """Configure SSH client for legacy algorithm support"""
        # Your original algorithm configuration but expanded for more legacy support
        paramiko.Transport._preferred_kex = (
            # Legacy KEX algorithms first for old devices
            "diffie-hellman-group1-sha1",  # Very old devices
            "diffie-hellman-group14-sha1",  # Older but more secure
            "diffie-hellman-group-exchange-sha1",
            "diffie-hellman-group-exchange-sha256",
            # Modern algorithms
            "ecdh-sha2-nistp256",
            "ecdh-sha2-nistp384",
            "ecdh-sha2-nistp521",
            "curve25519-sha256",
            "curve25519-sha256@libssh.org",
            "diffie-hellman-group16-sha512",
            "diffie-hellman-group18-sha512"
        )

        paramiko.Transport._preferred_ciphers = (
            # Legacy ciphers first
            "aes128-cbc",  # Very common on legacy
            "aes256-cbc",
            "3des-cbc",  # Very old devices
            "aes192-cbc",
            # Modern ciphers
            "aes128-ctr",
            "aes192-ctr",
            "aes256-ctr",
            "aes256-gcm@openssh.com",
            "aes128-gcm@openssh.com",
            "chacha20-poly1305@openssh.com",
            "aes256-gcm",
            "aes128-gcm"
        )

        paramiko.Transport._preferred_keys = (
            # Legacy key types first
            "ssh-rsa",  # Most compatible
            "ssh-dss",  # Very old devices
            # Modern key types
            "ecdsa-sha2-nistp256",
            "ecdsa-sha2-nistp384",
            "ecdsa-sha2-nistp521",
            "ssh-ed25519",
            "rsa-sha2-256",
            "rsa-sha2-512"
        )

    @staticmethod
    def create_legacy_connection_params(options):
        """Create connection parameters optimized for legacy devices"""
        connect_params = {
            'hostname': options.host,
            'port': options.port,
            'username': options.username,
            'password': options.password,
            'timeout': options.timeout,
            'allow_agent': False,
            'look_for_keys': False,
            'compress': False,  # Some legacy devices have issues with compression
        }

        if options.legacy_mode:
            # Additional legacy-specific parameters
            connect_params.update({
                'gss_auth': False,
                'gss_kex': False,
                'disabled_algorithms': {
                    # Disable algorithms that might cause issues on very old devices
                    'pubkeys': ['rsa-sha2-256', 'rsa-sha2-512'] if options.legacy_mode else [],
                }
            })

        return connect_params

    @staticmethod
    def legacy_prompt_detection(ssh_client, buffer_content, legacy_patterns=None):
        """Legacy-compatible prompt detection similar to your original script"""
        if legacy_patterns is None:
            legacy_patterns = [
                r'([^\r\n]*[#>$%])\s*$',  # Basic prompt endings
                r'([^\r\n]*[#>$%])\s*[\r\n]*$',  # With optional newlines
                r'([A-Za-z0-9\-_.]+[#>$%])\s*$',  # Hostname-style prompts
                r'([A-Za-z0-9\-_.@]+[#>$%])\s*$',  # With @ for user@host style
            ]

        lines = buffer_content.split('\n')
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue

            for pattern in legacy_patterns:
                match = re.search(pattern, line)
                if match:
                    prompt = match.group(1).strip()
                    # Additional validation - common for network devices
                    if any(line.endswith(char) for char in ['#', '>', '$', '%', ':', ']', ')']):
                        return prompt
        return None

    @staticmethod
    def apply_legacy_ssh_workarounds(ssh_client):
        """Apply workarounds for common legacy device issues"""
        try:
            # Some legacy devices need specific transport settings
            transport = ssh_client.get_transport()
            if transport:
                # Disable some features that can cause issues
                transport.use_compression(False)

                # Set keepalive for devices that drop connections
                transport.set_keepalive(30)

        except Exception as e:
            # Don't fail if workarounds can't be applied
            pass


# Enhancement to the main SSHClient class
class SSHClientLegacyMixin:
    """Mixin to add legacy support to your existing SSHClient"""

    def connect_with_legacy_support(self):
        """Enhanced connect method with legacy device support"""
        self._log_with_timestamp(
            f"Connecting to {self._options.host}:{self._options.port} (legacy mode: {self._options.legacy_mode})...",
            True)

        # Create SSH client with legacy algorithm support
        self._ssh_client = paramiko.SSHClient()

        if self._options.disable_host_key_checking or self._options.legacy_mode:
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        else:
            self._ssh_client.load_system_host_keys()
            self._ssh_client.set_missing_host_key_policy(paramiko.RejectPolicy())

        # Configure legacy algorithms if needed
        if self._options.legacy_algorithms:
            LegacySSHClientEnhancements.configure_legacy_algorithms(self._ssh_client)

        try:
            # Get connection parameters
            connect_params = LegacySSHClientEnhancements.create_legacy_connection_params(self._options)

            # Connect with retries for flaky legacy devices
            max_retries = 3 if self._options.legacy_mode else 1
            for attempt in range(max_retries):
                try:
                    self._ssh_client.connect(**connect_params)
                    break
                except (paramiko.AuthenticationException, paramiko.SSHException) as e:
                    if attempt == max_retries - 1:
                        raise
                    self._log_with_timestamp(f"Connection attempt {attempt + 1} failed, retrying...")
                    time.sleep(2)

            # Apply legacy workarounds
            LegacySSHClientEnhancements.apply_legacy_ssh_workarounds(self._ssh_client)

            self._log_with_timestamp(f"Connected to {self._options.host}:{self._options.port}", True)

            # Create shell if using shell mode
            if self._options.invoke_shell:
                self._create_shell_stream()

                # Use legacy prompt detection if enabled
                if self._options.legacy_prompt_detection and not self._options.prompt and not self._options.expect_prompt:
                    buffer_content = self._output_buffer.getvalue()
                    if buffer_content:
                        detected_prompt = LegacySSHClientEnhancements.legacy_prompt_detection(
                            self._ssh_client, buffer_content)
                        if detected_prompt:
                            self._options.expect_prompt = detected_prompt
                            self._log_with_timestamp(f"Legacy prompt detection: '{detected_prompt}'", True)

        except Exception as e:
            self._log_with_timestamp(f"Connection error: {str(e)}", True)
            raise

    def execute_command_with_legacy_support(self, command):
        """Enhanced command execution with legacy device support"""
        if self._options.legacy_mode:
            # Use more conservative timing for legacy devices
            original_shell_timeout = self._options.shell_timeout
            original_inter_command = self._options.inter_command_time

            # Adjust timing for legacy devices
            self._options.shell_timeout = max(self._options.shell_timeout, 3)
            self._options.inter_command_time = max(self._options.inter_command_time, 0.5)

        try:
            # Use your existing command execution logic
            result = self.execute_command(command)
            return result
        finally:
            if self._options.legacy_mode:
                # Restore original timing
                self._options.shell_timeout = original_shell_timeout
                self._options.inter_command_time = original_inter_command




class SSHClient:
    def __init__(self, options):
        self._options = options
        self._ssh_client = None
        self._shell = None
        self._output_buffer = StringIO()
        self._prompt_detected = False
        self._proxy_client = None
        self.router = None
        if self._options.routing_enabled and self._options.routing_rules:
            self.router = SimpleSSHRouter(self._options.routing_rules)

        # Validate required options
        if not options.host:
            raise ValueError("Host is required")
        if not options.username:
            raise ValueError("Username is required")
        if not options.password:
            raise ValueError("Password is required")

    def _recv_filtered(self, size=4096):
        """
        Receive data from shell with ANSI filtering applied immediately

        Args:
            size (int): Buffer size

        Returns:
            str: Filtered data
        """
        if not self._shell or not self._shell.recv_ready():
            return ""

        try:
            raw_data = self._shell.recv(size).decode('utf-8', errors='replace')
            filtered_data = filter_ansi_sequences(raw_data)

            # Optional: log filtering stats
            if self._options.debug and len(raw_data) != len(filtered_data):
                chars_filtered = len(raw_data) - len(filtered_data)
                self._log_with_timestamp(f"Filtered {chars_filtered} ANSI characters")

            return filtered_data
        except Exception as e:
            self._log_with_timestamp(f"Error reading from shell: {str(e)}")
            return ""

    def _log_with_timestamp(self, message, always_print=False):
        """Helper method to log with timestamp"""
        # Use datetime instead of time.strftime for microsecond support
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        timestamped_message = "[{}] {}".format(timestamp, message)

        if self._options.debug or always_print:
            print(timestamped_message)

        self._log_message(timestamped_message)

    def find_prompt(self, attempt_count=5, timeout=5):
        """Auto-detect command prompt with ANSI filtering"""
        if not self._shell:
            raise RuntimeError("Shell not initialized")

        self._log_with_timestamp("Attempting to auto-detect command prompt with ANSI filtering...", True)

        # Clear buffer
        self._output_buffer = StringIO()
        buffer = ""

        # Clear pending data
        while self._shell.recv_ready():
            self._recv_filtered()  # Just discard

        # Send newline to trigger prompt
        self._log_with_timestamp("Sending single newline to trigger prompt")
        self._shell.send("\n")
        time.sleep(3)

        # Collect filtered output
        buffer = ""
        start_time = time.time()

        while time.time() - start_time < 3:
            if self._shell.recv_ready():
                filtered_data = self._recv_filtered()
                if filtered_data:
                    buffer += filtered_data
                    self._output_buffer.write(filtered_data)
            else:
                time.sleep(0.1)

        # Extract prompt from filtered buffer
        prompt = self._extract_clean_prompt(buffer)
        if prompt:
            self._log_with_timestamp(f"Detected prompt: '{prompt}'", True)
            return prompt

        # Try additional attempts
        for i in range(attempt_count):
            self._log_with_timestamp(f"Prompt detection attempt {i + 1}/{attempt_count}")

            buffer = ""
            self._shell.send("\n")

            start_time = time.time()
            while time.time() - start_time < timeout:
                if self._shell.recv_ready():
                    filtered_data = self._recv_filtered()
                    if filtered_data:
                        buffer += filtered_data
                        self._output_buffer.write(filtered_data)
                        self._options.output_callback(filtered_data)
                else:
                    if buffer:
                        prompt = self._extract_clean_prompt(buffer)
                        if prompt:
                            self._log_with_timestamp(f"Detected prompt: '{prompt}'", True)
                            return prompt
                    time.sleep(0.1)

            if buffer:
                prompt = self._extract_clean_prompt(buffer)
                if prompt:
                    self._log_with_timestamp(f"Extracted prompt: '{prompt}'", True)
                    return prompt

        # Last resort
        self._log_with_timestamp("Could not detect prompt, using default '#'")
        return '#'

    def _extract_clean_prompt(self, buffer):
        """
        Extract a clean prompt from buffer, handling cases where the prompt is repeated.

        Args:
            buffer (str): The buffer containing potential prompts

        Returns:
            str: A clean, single instance of the prompt
        """
        if not buffer or not buffer.strip():
            return None

        # Remove ANSI escape sequences
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_buffer = ansi_escape.sub('', buffer)

        # Get non-empty lines
        lines = [line.strip() for line in clean_buffer.split('\n') if line.strip()]
        if not lines:
            return None

        # Look for repeated patterns in the last line
        last_line = lines[-1]

        # Common prompt ending characters
        common_endings = ['#', '>', '$', '%', ':', '~]', ']', '}', ')', '|']

        # First check if the last line is a simple prompt (no repetition)
        if any(last_line.endswith(char) for char in common_endings) and len(last_line) < 30:
            if not self._is_repeated_prompt(last_line):
                return last_line

        # Check for repetitions (like 'device# device# device#')
        base_prompt = self._extract_base_prompt(last_line)
        if base_prompt:
            self._log_with_timestamp(f"Extracted base prompt from repeated pattern: '{base_prompt}'")
            return base_prompt

        # If the last line doesn't have repetitions but looks like a prompt
        for line in reversed(lines):
            if any(line.endswith(char) for char in common_endings):
                base_prompt = self._extract_base_prompt(line)
                if base_prompt:
                    return base_prompt
                return line

        # Last resort - try to find anything that looks like a prompt in any line
        for line in reversed(lines):
            # Check if line looks like a hostname or path with prompt char
            if len(line) < 50:  # Not too long
                for ending in common_endings:
                    if ending in line:
                        parts = line.split(ending)
                        # If there are multiple parts and the last isn't empty (like in 'device#')
                        if len(parts) > 1 and not parts[-1].strip():
                            # Get the part before the last prompt char
                            base = parts[0].strip()
                            for i in range(1, len(parts) - 1):
                                base += ending + parts[i].strip()
                            return base + ending

        # If all else fails, just use the last line
        return lines[-1]

    def _is_repeated_prompt(self, text):
        """Check if text contains repeated prompt patterns."""
        parts = re.split(r'[#>$%:]', text)
        # If there are multiple parts with similar text, it's likely a repeated prompt
        if len(parts) > 2:
            base_parts = [part.strip() for part in parts if part.strip()]
            if len(base_parts) > 1 and len(set(base_parts)) == 1:
                return True
        return False

    def _extract_base_prompt(self, text):
        """
        Extract a base prompt from text that might contain repetitions.
        Example: 'device# device# device#' -> 'device#'
        """
        # Find common ending characters
        for char in ['#', '>', '$', '%', ':', '~]', ']', '}', ')', '|']:
            if char in text:
                # Split by the prompt character
                parts = text.split(char)
                if len(parts) > 1:
                    # Check if the parts before the character look similar
                    base_parts = [part.strip() for part in parts[:-1]]
                    if base_parts and all(part == base_parts[0] for part in base_parts):
                        # Found a repetition pattern, return just one instance
                        return base_parts[0] + char

        # Look for repeated whitespace-separated patterns
        parts = text.split()
        if len(parts) > 1:
            # Check for repeating segments
            potential_prompts = []
            for part in parts:
                if any(part.endswith(char) for char in ['#', '>', '$', '%', ':', '~]', ']', '}', ')', '|']):
                    potential_prompts.append(part)

            # If we found multiple segments that look like prompts and they're identical
            if len(potential_prompts) > 1 and len(set(potential_prompts)) == 1:
                return potential_prompts[0]

        return None

    def _create_shell_stream(self):
        """Create interactive shell stream with ANSI filtering"""
        self._log_with_timestamp("Creating shell stream with ANSI filtering")

        if self._shell:
            self._log_with_timestamp("Shell stream already exists, reusing")
            return

        self._shell = self._ssh_client.invoke_shell()
        self._shell.settimeout(self._options.timeout)

        # Wait for shell initialization
        self._log_with_timestamp("SSHClient Message: Waiting for shell initialization (2000ms)")
        time.sleep(2)

        # Read initial output with filtering
        if self._shell.recv_ready():
            filtered_data = self._recv_filtered()
            if filtered_data:
                self._output_buffer.write(filtered_data)
                self._options.output_callback(filtered_data)

    def execute_command(self, command):
        """Execute command on the remote device"""
        if not self._ssh_client or not self._ssh_client.get_transport() or not self._ssh_client.get_transport().is_active():
            raise RuntimeError("SSH client is not connected")

        # Only warn if using shell mode with no prompt information
        if self._options.invoke_shell and not self._options.prompt and not self._options.expect_prompt:
            self._log_with_timestamp(
                "WARNING: Executing shell command with no prompt pattern or expect prompt defined!", True)

        self._log_with_timestamp("SSHClient Message: Executing command: '{}'".format(command), True)
        start_time = time.time()

        if self._options.invoke_shell:
            # Handle multiple comma-separated commands for shell mode
            commands = command.split(',')
            result = self._execute_shell_commands(commands)
        else:
            result = self._execute_direct_command(command)

        # Wait between commands if specified
        if self._options.inter_command_time > 0:
            self._log_with_timestamp(
                "SSHClient Message: Waiting between commands: {}s".format(self._options.inter_command_time))
            time.sleep(self._options.inter_command_time)

        duration = time.time() - start_time
        self._log_with_timestamp("SSHClient Message: Command execution completed in {:.2f}ms".format(duration * 1000), True)

        return result

    def _execute_direct_command(self, command):
        """Execute command directly (non-interactive)"""
        self._log_with_timestamp("Using direct command execution mode")
        start_time = time.time()

        stdin, stdout, stderr = self._ssh_client.exec_command(
            command,
            timeout=self._options.timeout
        )

        result = stdout.read().decode('utf-8', errors='replace')
        error = stderr.read().decode('utf-8', errors='replace')

        execution_time = time.time() - start_time
        self._log_with_timestamp("Command execution took {:.2f}ms".format(execution_time * 1000))

        self._options.output_callback(result)

        if error:
            self._log_with_timestamp("Command produced error output: {}".format(error), True)
            self._options.error_callback(error)

        self._log_message(result)
        if error:
            self._log_message(error)

        return result

    def _scrub_prompt(self, raw_prompt):
        """
        Clean up a detected prompt to get just the prompt pattern without command outputs or extra whitespace.

        Args:
            raw_prompt (str): The raw detected prompt string that may contain command output

        Returns:
            str: The cleaned prompt string
        """
        self._log_with_timestamp(f"Raw detected prompt: '{raw_prompt}'")

        # Multiple approaches to extract the actual prompt:

        # 1. Try to find the last line with a prompt character
        lines = raw_prompt.strip().split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]

        # Look through lines in reverse to find the first one that looks like a prompt
        for line in reversed(cleaned_lines):
            # Common prompt ending characters
            if line.endswith('#') or line.endswith('>') or line.endswith('$') or line.endswith('%'):
                # Check if this is a simple prompt or contains a command
                if ' ' in line:
                    # This might be a line with both command and prompt
                    # Try to extract just the prompt part
                    parts = line.split()
                    # If the last part ends with a prompt character, it might be the prompt
                    if parts[-1][-1] in '#>$%':
                        self._log_with_timestamp(f"Extracted prompt from command line: '{parts[-1]}'")
                        return parts[-1]

                    # Otherwise, try to find the last occurrence of the prompt pattern
                    prompt_chars = ['#', '>', '$', '%']
                    for char in prompt_chars:
                        if char in line:
                            # Split by the prompt character and take the first part + the character
                            prompt_parts = line.split(char)
                            if len(prompt_parts) > 1:
                                potential_prompt = prompt_parts[0] + char
                                # Check if this looks like a valid prompt (not too long, no spaces at specific positions)
                                if len(potential_prompt) < 30 and ' ' not in potential_prompt[-15:]:
                                    self._log_with_timestamp(
                                        f"Extracted prompt by character split: '{potential_prompt}'")
                                    return potential_prompt
                else:
                    # This looks like a clean prompt
                    self._log_with_timestamp(f"Found clean prompt line: '{line}'")
                    return line

        # 2. Fallback: Try regex extraction on the whole string
        prompt_patterns = [
            r'(\S+[#>$%])\s*$',  # Basic prompt at the end of the string
            r'((?:[A-Za-z0-9_\-]+(?:\([^\)]+\))?)?[#>$%])\s*$',  # Handle context in parentheses like router(config)#
            r'(\S+@\S+[#>$%])\s*$'  # username@host style prompts
        ]

        for pattern in prompt_patterns:
            match = re.search(pattern, raw_prompt)
            if match:
                extracted = match.group(1)
                self._log_with_timestamp(f"Extracted prompt via regex: '{extracted}'")
                return extracted

        # 3. Last resort: just return the last line if it's not too long
        if cleaned_lines and len(cleaned_lines[-1]) < 50:  # Arbitrary length limit for sanity
            self._log_with_timestamp(f"Using last line as prompt: '{cleaned_lines[-1]}'")
            return cleaned_lines[-1]

        # If all else fails, return the original but warn
        self._log_with_timestamp(f"WARNING: Could not scrub prompt, using as-is: '{raw_prompt}'", True)
        return raw_prompt

    def _execute_shell_commands(self, commands):
        """Execute commands in interactive shell mode with ANSI filtering"""
        self._log_with_timestamp("Using shell mode for command execution with ANSI filtering")
        start_time = time.time()

        if not self._shell:
            self._log_with_timestamp("Shell stream not initialized, creating now")
            self._create_shell_stream()

        # Clear buffer and reset prompt detection flag
        self._output_buffer = StringIO()
        self._prompt_detected = False

        try:
            # Only process commands if there are meaningful commands to send
            has_commands = any(cmd.strip() for cmd in commands)

            if has_commands:
                # Process each command
                for i, cmd in enumerate(commands):
                    if not cmd.strip() or cmd.strip() == "\\n":
                        self._log_with_timestamp("Sending newline command {}/{}".format(i + 1, len(commands)))
                        self._shell.send('\n')
                    else:
                        self._log_with_timestamp("Sending command {}/{}: '{}'".format(i + 1, len(commands), cmd))
                        self._shell.send(cmd + '\n')

                    # Wait between commands
                    if self._options.inter_command_time > 0 and i < len(commands) - 1:
                        self._log_with_timestamp(
                            "Waiting between sub-commands: {}s".format(self._options.inter_command_time))
                        time.sleep(self._options.inter_command_time)

                # PROMPT COUNTING WITH ANSI FILTERING
                if self._options.expect_prompt:
                    expected_prompts = self._options.prompt_count
                    found_prompts = 0
                    accumulated_buffer = ""

                    self._log_with_timestamp("Monitoring for EXACTLY {} occurrences of: '{}'".format(
                        expected_prompts, self._options.expect_prompt))

                    timeout_ms = self._options.expect_prompt_timeout
                    timeout_time = time.time() + timeout_ms / 1000

                    while found_prompts < expected_prompts and time.time() < timeout_time:
                        if self._shell.recv_ready():
                            try:
                                # Use the filtered receive method
                                filtered_data = self._recv_filtered()
                                if filtered_data:
                                    accumulated_buffer += filtered_data
                                    self._output_buffer.write(filtered_data)
                                    self._options.output_callback(filtered_data)

                                    # Count prompts in filtered buffer
                                    current_count = accumulated_buffer.count(self._options.expect_prompt)

                                    if current_count > found_prompts:
                                        found_prompts = current_count
                                        self._log_with_timestamp(
                                            "PROMPT DETECTED: {}/{}".format(found_prompts, expected_prompts))

                                        if found_prompts >= expected_prompts:
                                            self._log_with_timestamp(
                                                "TARGET REACHED: {} prompts detected. STOPPING NOW.".format(
                                                    found_prompts))
                                            break

                            except Exception as e:
                                self._log_with_timestamp("Error reading output: {}".format(str(e)))
                                continue
                        else:
                            time.sleep(0.01)

                    # Final status
                    if found_prompts >= expected_prompts:
                        self._log_with_timestamp(
                            "SUCCESS: Command execution completed with {}/{} prompts".format(found_prompts,
                                                                                             expected_prompts), True)
                    else:
                        self._log_with_timestamp(
                            "TIMEOUT: Only detected {}/{} prompts after {}ms".format(found_prompts, expected_prompts,
                                                                                     timeout_ms), True)
                else:
                    # Timeout-based approach with filtering
                    self._log_with_timestamp(
                        "No expect prompt defined, waiting shell timeout: {}s".format(self._options.shell_timeout))
                    time.sleep(self._options.shell_timeout)

                    # Read remaining data with filtering
                    while self._shell.recv_ready():
                        filtered_data = self._recv_filtered()
                        if filtered_data:
                            self._output_buffer.write(filtered_data)
                            self._options.output_callback(filtered_data)

                self._log_with_timestamp("Shell command execution completed")
            else:
                self._log_with_timestamp("No commands to execute, skipping shell command execution")

        except Exception as e:
            error_message = "Error during shell execution: {}".format(str(e))
            self._log_with_timestamp(error_message, True)
            self._log_message(error_message)
            self._options.error_callback(error_message)

        total_time = time.time() - start_time
        self._log_with_timestamp("Total shell command execution time: {:.2f}ms".format(total_time * 1000))

        return self._output_buffer.getvalue()

    def set_expect_prompt(self, prompt_string):
        """Set the expected prompt string"""
        if prompt_string:
            self._options.expect_prompt = prompt_string
            self._log_with_timestamp("Expect prompt set to: '{}'".format(prompt_string), True)

    def connect(self):
        """Enhanced connect method with routing support"""
        self._log_with_timestamp("Connecting to {}:{}...".format(self._options.host, self._options.port), True)

        # Determine routing decision
        route_action = 'direct'  # Default
        if self.router:
            route_action = self.router.resolve_route(self._options.host, self._options.port)
            self._log_with_timestamp(f"Routing decision: {route_action}", True)

        if route_action == 'deny':
            raise ConnectionError(f"Connection to {self._options.host}:{self._options.port} denied by routing policy")

        try:
            if route_action == 'proxy':
                self._connect_through_proxy()
            else:
                self._connect_direct()

            self._log_with_timestamp("Connected to {}:{}".format(self._options.host, self._options.port), True)

            # Create shell if we're using shell mode
            if self._options.invoke_shell:
                self._create_shell_stream()

                # Check if a prompt pattern is defined
                if not self._options.prompt and not self._options.expect_prompt:
                    self._log_with_timestamp(
                        "WARNING: No prompt pattern or expect prompt defined. Shell commands may not work correctly!",
                        True)

        except Exception as e:
            self._log_with_timestamp("Connection error: {}".format(str(e)), True)
            raise

    def _connect_direct(self):
        """Direct connection (your existing logic)"""
        self._ssh_client = paramiko.SSHClient()
        self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Apply legacy support if needed
        if self._options.legacy_mode:
            LegacySSHClientEnhancements.configure_legacy_algorithms(self._ssh_client)

        self._ssh_client.connect(
            hostname=self._options.host,
            port=self._options.port,
            username=self._options.username,
            password=self._options.password,
            timeout=self._options.timeout,
            allow_agent=False,
            look_for_keys=False
        )

    def _connect_through_proxy(self):
        """Connect through SSH proxy using environment settings"""
        if not self._options.proxy_host:
            raise ValueError("Proxy connection requested but SSH_PROXY_HOST not set")

        self._log_with_timestamp(
            f"Connecting via proxy: {self._options.proxy_username}@{self._options.proxy_host}:{self._options.proxy_port}")

        # Step 1: Connect to proxy
        self._proxy_client = paramiko.SSHClient()
        self._proxy_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Apply legacy support to proxy connection if needed
        if self._options.legacy_mode:
            LegacySSHClientEnhancements.configure_legacy_algorithms(self._proxy_client)

        # Authenticate to proxy
        if self._options.proxy_key_path:
            proxy_key = paramiko.RSAKey(filename=self._options.proxy_key_path)
            self._proxy_client.connect(
                hostname=self._options.proxy_host,
                port=self._options.proxy_port,
                username=self._options.proxy_username,
                pkey=proxy_key,
                timeout=self._options.timeout
            )
        else:
            self._proxy_client.connect(
                hostname=self._options.proxy_host,
                port=self._options.proxy_port,
                username=self._options.proxy_username,
                password=self._options.proxy_password,
                timeout=self._options.timeout
            )

        self._log_with_timestamp("Connected to proxy, creating tunnel...")

        # Step 2: Create tunnel through proxy
        transport = self._proxy_client.get_transport()
        dest_addr = (self._options.host, self._options.port)
        local_addr = ('localhost', 0)
        tunnel_channel = transport.open_channel('direct-tcpip', dest_addr, local_addr)

        # Step 3: Connect to final destination through tunnel
        self._ssh_client = paramiko.SSHClient()
        self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Apply legacy support to final connection if needed
        if self._options.legacy_mode:
            LegacySSHClientEnhancements.configure_legacy_algorithms(self._ssh_client)

        self._ssh_client.connect(
            hostname=self._options.host,
            port=self._options.port,
            username=self._options.username,
            password=self._options.password,
            timeout=self._options.timeout,
            allow_agent=False,
            look_for_keys=False,
            sock=tunnel_channel  # This is the key - route through tunnel!
        )

        self._log_with_timestamp("Established connection through proxy tunnel")

    def disconnect(self):
        """Enhanced disconnect to handle proxy connections"""
        self._log_with_timestamp("Disconnecting from device")

        try:
            if self._shell:
                self._shell.close()
                self._shell = None

            if self._ssh_client:
                self._ssh_client.close()

            # Clean up proxy connection
            if self._proxy_client:
                self._proxy_client.close()
                self._proxy_client = None

            self._log_with_timestamp("Successfully disconnected")
        except Exception as e:
            self._log_with_timestamp("Error during disconnect: {}".format(str(e)), True)

    def _log_message(self, message):
        """Log message to file if log file is specified"""
        if not self._options.log_file:
            return

        try:
            # Ensure directory exists
            log_dir = os.path.dirname(self._options.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)

            with open(self._options.log_file, 'a') as f:
                f.write(message + '\n')
                f.flush()
        except Exception as e:
            self._options.error_callback("Error writing to log file: {}".format(str(e)))