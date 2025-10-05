# app/blueprints/auth/auth_manager.py
"""
Authentication manager supporting LDAP, local (Windows/Linux), and SSH fallback authentication
"""
import os
import platform
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AuthResult:
    """Authentication result with user details"""
    success: bool
    username: str
    groups: List[str] = None
    error: str = None
    auth_method: str = None

    def __post_init__(self):
        if self.groups is None:
            self.groups = []


class AuthenticationManager:
    """
    Unified authentication manager supporting multiple backends:
    - Windows local authentication (via win32security)
    - Linux/Unix local authentication (via PAM with SSH fallback)
    - LDAP/Active Directory authentication
    """

    def __init__(self, config: dict = None):
        """
        Initialize authentication manager with configuration

        Args:
            config: Dictionary with authentication configuration
                   Falls back to environment variables and defaults
        """
        self.config = config or {}
        self.system = platform.system()

        # Determine available authentication methods
        self._setup_auth_methods()

        logger.info(f"Authentication manager initialized on {self.system}")
        logger.info(f"Available methods: {self.available_methods}")

    def _setup_auth_methods(self):
        """Detect and configure available authentication methods"""
        self.available_methods = []

        # Check for local authentication support
        if self.system == "Windows":
            try:
                import win32security
                self.available_methods.append("local")
                self._windows_auth_available = True
                logger.info("Windows authentication available")
            except ImportError:
                self._windows_auth_available = False
                logger.warning("Windows authentication unavailable (pywin32 not installed)")
        else:
            # On Linux, we can use either PAM or SSH fallback
            self.available_methods.append("local")

            try:
                import pam
                self._pam_auth_available = True
                logger.info("PAM authentication available")
            except ImportError:
                self._pam_auth_available = False
                logger.info("PAM authentication unavailable, will use SSH fallback")

            # Check if SSH fallback is enabled
            self._ssh_fallback_enabled = self.config.get('local', {}).get('use_ssh_fallback', True)
            if self._ssh_fallback_enabled:
                try:
                    import paramiko
                    self._ssh_available = True
                    logger.info("SSH fallback authentication available")
                except ImportError:
                    self._ssh_available = False
                    logger.warning("SSH fallback unavailable (paramiko not installed)")

        # Check for LDAP support
        ldap_enabled = self.config.get('ldap', {}).get('enabled', False)
        if ldap_enabled:
            try:
                import ldap3
                self.available_methods.append("ldap")
                self._ldap_available = True
                logger.info("LDAP authentication available")
            except ImportError:
                self._ldap_available = False
                logger.warning("LDAP authentication unavailable (ldap3 not installed)")
        else:
            self._ldap_available = False

    def authenticate(self,
                     username: str,
                     password: str,
                     auth_method: str = None,
                     domain: str = None) -> AuthResult:
        """
        Authenticate user with specified method

        Args:
            username: Username
            password: Password
            auth_method: Authentication method ('local' or 'ldap')
                        If None, uses default from config
            domain: Domain for Windows authentication (optional)

        Returns:
            AuthResult with authentication outcome
        """
        # Determine authentication method
        if auth_method is None:
            auth_method = self.config.get('default_method', 'local')

        if auth_method not in self.available_methods:
            return AuthResult(
                success=False,
                username=username,
                error=f"Authentication method '{auth_method}' not available",
                auth_method=auth_method
            )

        # Route to appropriate authentication handler
        if auth_method == "local":
            return self._authenticate_local(username, password, domain)
        elif auth_method == "ldap":
            return self._authenticate_ldap(username, password)
        else:
            return AuthResult(
                success=False,
                username=username,
                error=f"Unknown authentication method: {auth_method}",
                auth_method=auth_method
            )

    def _authenticate_local(self,
                            username: str,
                            password: str,
                            domain: str = None) -> AuthResult:
        """Authenticate against local system (Windows or Linux)"""
        if self.system == "Windows" and self._windows_auth_available:
            return self._authenticate_windows(username, password, domain)
        elif self._pam_auth_available:
            return self._authenticate_pam(username, password)
        elif self._ssh_fallback_enabled and self._ssh_available:
            logger.info(f"Using SSH fallback for {username}")
            return self._authenticate_ssh_fallback(username, password)
        else:
            return AuthResult(
                success=False,
                username=username,
                error="Local authentication not available on this system",
                auth_method="local"
            )

    def _authenticate_windows(self,
                              username: str,
                              password: str,
                              domain: str = None) -> AuthResult:
        """Authenticate against Windows using win32security"""
        import win32security
        import win32con

        try:
            # Determine domain
            if domain is None:
                domain_required = self.config.get('local', {}).get('domain_required', False)
                if domain_required:
                    return AuthResult(
                        success=False,
                        username=username,
                        error="Domain required for Windows authentication",
                        auth_method="local"
                    )

                # Use computer name as domain if configured
                use_computer_name = self.config.get('local', {}).get(
                    'use_computer_name_as_domain', True
                )
                if use_computer_name:
                    domain = os.environ.get('COMPUTERNAME', 'WORKGROUP')

            # Attempt authentication
            handle = win32security.LogonUser(
                username,
                domain,
                password,
                win32con.LOGON32_LOGON_NETWORK,
                win32con.LOGON32_PROVIDER_DEFAULT
            )

            # Get groups if successful
            groups = self._get_windows_groups(handle, username, domain)

            # Create filesystem-safe username
            safe_username = f"{domain}@{username}".replace('\\', '@')

            return AuthResult(
                success=True,
                username=safe_username,
                groups=groups,
                auth_method="local"
            )

        except Exception as e:
            logger.error(f"Windows authentication failed for {username}: {e}")
            return AuthResult(
                success=False,
                username=username,
                error=str(e),
                auth_method="local"
            )

    def _get_windows_groups(self, handle, username: str, domain: str) -> List[str]:
        """Extract Windows group memberships"""
        try:
            import win32security
            import win32net

            groups = []
            try:
                user_info = win32net.NetUserGetLocalGroups(domain, username)
                groups = [group for group in user_info]
            except Exception as e:
                logger.warning(f"Could not retrieve groups for {username}: {e}")

            return groups
        except Exception as e:
            logger.error(f"Error getting Windows groups: {e}")
            return []

    def _authenticate_pam(self, username: str, password: str) -> AuthResult:
        """Authenticate against Linux/Unix PAM with SSH fallback"""
        try:
            import pam

            p = pam.pam()
            if p.authenticate(username, password):
                # Get groups
                groups = self._get_unix_groups(username)

                return AuthResult(
                    success=True,
                    username=username,
                    groups=groups,
                    auth_method="local"
                )
            else:
                return AuthResult(
                    success=False,
                    username=username,
                    error="Invalid credentials",
                    auth_method="local"
                )
        except ImportError:
            logger.warning("PAM not available, trying SSH fallback")
            if self._ssh_fallback_enabled and self._ssh_available:
                return self._authenticate_ssh_fallback(username, password)
            else:
                return AuthResult(
                    success=False,
                    username=username,
                    error="PAM not available and SSH fallback disabled",
                    auth_method="local"
                )
        except Exception as e:
            logger.warning(f"PAM authentication failed for {username}: {e}")
            # Try SSH fallback on PAM failure
            if self._ssh_fallback_enabled and self._ssh_available:
                logger.info(f"Attempting SSH fallback for {username}")
                return self._authenticate_ssh_fallback(username, password)
            else:
                return AuthResult(
                    success=False,
                    username=username,
                    error=str(e),
                    auth_method="local"
                )

    def _authenticate_ssh_fallback(self, username: str, password: str) -> AuthResult:
        """Fallback to SSH authentication if PAM fails or is unavailable"""
        try:
            import paramiko

            # Get SSH host from config (default to localhost)
            ssh_host = self.config.get('local', {}).get('ssh_host', 'localhost')
            ssh_port = self.config.get('local', {}).get('ssh_port', 22)

            # Try to SSH to configured host
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                hostname=ssh_host,
                port=ssh_port,
                username=username,
                password=password,
                timeout=5,
                look_for_keys=False,
                allow_agent=False
            )

            # If connection succeeds, auth is valid
            ssh.close()

            # Get groups
            groups = self._get_unix_groups(username)

            logger.info(f"SSH fallback authentication successful for {username}")

            return AuthResult(
                success=True,
                username=username,
                groups=groups,
                auth_method="local"
            )

        except Exception as e:
            # Check if it's specifically an auth failure
            error_str = str(e).lower()
            if 'authentication' in error_str or 'password' in error_str:
                logger.warning(f"SSH fallback authentication failed for {username}: Invalid credentials")
                return AuthResult(
                    success=False,
                    username=username,
                    error="Invalid credentials",
                    auth_method="local"
                )
            else:
                logger.error(f"SSH fallback connection error for {username}: {e}")
                return AuthResult(
                    success=False,
                    username=username,
                    error=f"SSH authentication error: {str(e)}",
                    auth_method="local"
                )

    def _get_unix_groups(self, username: str) -> List[str]:
        """Extract Unix group memberships"""
        try:
            import grp
            import pwd

            groups = []
            user_info = pwd.getpwnam(username)
            primary_gid = user_info.pw_gid

            # Add primary group
            try:
                primary_group = grp.getgrgid(primary_gid).gr_name
                groups.append(primary_group)
            except KeyError:
                pass

            # Add supplementary groups
            for group in grp.getgrall():
                if username in group.gr_mem:
                    groups.append(group.gr_name)

            return groups
        except Exception as e:
            logger.error(f"Error getting Unix groups: {e}")
            return []

    def _authenticate_ldap(self, username: str, password: str) -> AuthResult:
        """Authenticate against LDAP/Active Directory"""
        if not self._ldap_available:
            return AuthResult(
                success=False,
                username=username,
                error="LDAP authentication not available",
                auth_method="ldap"
            )

        from ldap3 import Server, Connection, ALL, SUBTREE
        from ldap3.core.exceptions import LDAPException

        ldap_config = self.config.get('ldap', {})

        try:
            # Connect to LDAP server
            server_uri = ldap_config.get('server')
            port = ldap_config.get('port', 389)
            use_ssl = ldap_config.get('use_ssl', False)

            server = Server(
                server_uri,
                port=port,
                use_ssl=use_ssl,
                get_info=ALL
            )

            # Build user DN from template
            user_dn_template = ldap_config.get('user_dn_template')
            user_dn = user_dn_template.format(username=username)

            # Attempt bind (authentication)
            conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True
            )

            # Get groups if configured
            groups = []
            if ldap_config.get('search_groups', False):
                groups = self._get_ldap_groups(conn, user_dn, ldap_config)

            conn.unbind()

            return AuthResult(
                success=True,
                username=username,
                groups=groups,
                auth_method="ldap"
            )

        except LDAPException as e:
            logger.error(f"LDAP authentication failed for {username}: {e}")
            return AuthResult(
                success=False,
                username=username,
                error=str(e),
                auth_method="ldap"
            )
        except Exception as e:
            logger.error(f"LDAP authentication error for {username}: {e}")
            return AuthResult(
                success=False,
                username=username,
                error=str(e),
                auth_method="ldap"
            )

    def _get_ldap_groups(self, conn, user_dn: str, ldap_config: dict) -> List[str]:
        """Extract LDAP group memberships"""
        try:
            from ldap3 import SUBTREE

            group_base_dn = ldap_config.get('group_base_dn')
            group_filter = ldap_config.get('group_filter',
                                           '(&(objectClass=group)(member={user_dn}))')

            # Replace user_dn placeholder in filter
            search_filter = group_filter.format(user_dn=user_dn)

            groups = []
            conn.search(
                search_base=group_base_dn,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=['cn']
            )

            for entry in conn.entries:
                if hasattr(entry, 'cn'):
                    groups.append(str(entry.cn))

            return groups

        except Exception as e:
            logger.error(f"Error getting LDAP groups: {e}")
            return []

    def get_available_methods(self) -> Dict:
        """Get information about available authentication methods"""
        return {
            'available_methods': self.available_methods,
            'default_method': self.config.get('default_method', 'local'),
            'system_info': {
                'system': self.system,
                'windows_auth_available': self._windows_auth_available if self.system == "Windows" else False,
                'pam_auth_available': getattr(self, '_pam_auth_available', False),
                'ssh_fallback_available': getattr(self, '_ssh_available', False),
                'ldap_available': self._ldap_available,
                'ldap_configured': self.config.get('ldap', {}).get('enabled', False)
            }
        }