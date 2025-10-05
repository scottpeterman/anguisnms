# app/config_loader.py
"""
Configuration loader for Anguis
Loads from config.yaml and environment variables (env vars take precedence)
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and merge configuration from YAML file and environment variables"""

    def __init__(self, config_file: str = 'config.yaml'):
        """
        Initialize configuration loader

        Args:
            config_file: Path to YAML configuration file
        """
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file and environment"""
        # Start with defaults
        config = self._get_defaults()

        # Load from YAML file if it exists
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    yaml_config = yaml.safe_load(f) or {}
                    config = self._merge_configs(config, yaml_config)
                logger.info(f"Loaded configuration from {self.config_file}")
            except Exception as e:
                logger.warning(f"Error loading config file {self.config_file}: {e}")
        else:
            logger.info(f"Config file {self.config_file} not found, using defaults")

        # Override with environment variables
        config = self._apply_env_overrides(config)

        return config

    def _get_defaults(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            'authentication': {
                'default_method': 'local',
                'local': {
                    'enabled': True,
                    'domain_required': False,
                    'use_computer_name_as_domain': True
                },
                'ldap': {
                    'enabled': False,
                    'server': None,
                    'port': 389,
                    'use_ssl': False,
                    'base_dn': None,
                    'user_dn_template': None,
                    'search_groups': False,
                    'group_base_dn': None,
                    'group_filter': '(&(objectClass=group)(member={user_dn}))',
                    'timeout': 10,
                    'max_retries': 3
                }
            },
            'flask': {
                'secret_key': None,  # Will be auto-generated if not provided
                'session_timeout_minutes': 120
            },
            'server': {
                'host': '0.0.0.0',
                'port': 8086,
                'debug': False
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file': None
            }
        }

    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge two configuration dictionaries"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _apply_env_overrides(self, config: Dict) -> Dict:
        """Apply environment variable overrides to configuration"""
        # Flask settings
        if os.getenv('FLASK_SECRET_KEY'):
            config['flask']['secret_key'] = os.getenv('FLASK_SECRET_KEY')

        if os.getenv('SESSION_TIMEOUT_MINUTES'):
            config['flask']['session_timeout_minutes'] = int(os.getenv('SESSION_TIMEOUT_MINUTES'))

        # Server settings
        if os.getenv('Anguis_HOST'):
            config['server']['host'] = os.getenv('Anguis_HOST')

        if os.getenv('Anguis_PORT'):
            config['server']['port'] = int(os.getenv('Anguis_PORT'))

        if os.getenv('Anguis_DEBUG'):
            config['server']['debug'] = os.getenv('Anguis_DEBUG').lower() in ('true', '1', 'yes')

        # Authentication settings
        if os.getenv('AUTH_DEFAULT_METHOD'):
            config['authentication']['default_method'] = os.getenv('AUTH_DEFAULT_METHOD')

        # LDAP settings
        if os.getenv('LDAP_ENABLED'):
            config['authentication']['ldap']['enabled'] = os.getenv('LDAP_ENABLED').lower() in ('true', '1', 'yes')

        if os.getenv('LDAP_SERVER'):
            config['authentication']['ldap']['server'] = os.getenv('LDAP_SERVER')

        if os.getenv('LDAP_PORT'):
            config['authentication']['ldap']['port'] = int(os.getenv('LDAP_PORT'))

        if os.getenv('LDAP_USE_SSL'):
            config['authentication']['ldap']['use_ssl'] = os.getenv('LDAP_USE_SSL').lower() in ('true', '1', 'yes')

        if os.getenv('LDAP_BASE_DN'):
            config['authentication']['ldap']['base_dn'] = os.getenv('LDAP_BASE_DN')

        if os.getenv('LDAP_USER_DN_TEMPLATE'):
            config['authentication']['ldap']['user_dn_template'] = os.getenv('LDAP_USER_DN_TEMPLATE')

        if os.getenv('LDAP_SEARCH_GROUPS'):
            config['authentication']['ldap']['search_groups'] = os.getenv('LDAP_SEARCH_GROUPS').lower() in (
            'true', '1', 'yes')

        if os.getenv('LDAP_GROUP_BASE_DN'):
            config['authentication']['ldap']['group_base_dn'] = os.getenv('LDAP_GROUP_BASE_DN')

        # Logging settings
        if os.getenv('LOG_LEVEL'):
            config['logging']['level'] = os.getenv('LOG_LEVEL').upper()

        if os.getenv('LOG_FILE'):
            config['logging']['file'] = os.getenv('LOG_FILE')

        return config

    def get(self, key_path: str, default=None):
        """
        Get configuration value by dot-separated path

        Args:
            key_path: Dot-separated path to config value (e.g., 'authentication.ldap.server')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_section(self, section: str) -> Dict:
        """
        Get entire configuration section

        Args:
            section: Section name (e.g., 'authentication', 'ldap')

        Returns:
            Configuration section dictionary
        """
        return self.config.get(section, {})


def load_config(config_file: str = 'config.yaml') -> Dict[str, Any]:
    """
    Convenience function to load configuration

    Args:
        config_file: Path to YAML configuration file

    Returns:
        Complete configuration dictionary
    """
    loader = ConfigLoader(config_file)
    return loader.config