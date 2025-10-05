# Anguis Authentication System

**Multi-Method Authentication for Enterprise Network Management**

Anguis supports flexible authentication with multiple backends: Windows local authentication, Linux/Unix PAM, and LDAP/Active Directory. This document covers the complete implementation, configuration, and usage.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Authentication Methods](#authentication-methods)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

---

## Overview

The Anguis authentication system provides:

- **Multiple Authentication Backends**
  - Windows local authentication (via pywin32)
  - Linux/Unix PAM authentication
  - LDAP/Active Directory integration
  
- **Flexible Configuration**
  - YAML-based configuration with environment variable overrides
  - Per-method configuration options
  - Automatic platform detection

- **Session Management**
  - Secure Flask sessions with configurable timeout
  - User group tracking
  - Authentication method tracking

- **Preserved UI**
  - Seamless integration with existing Anguis theme
  - Dynamic auth method selector (only shown when multiple methods available)
  - Theme support (light/dark/cyber)

---

## Architecture

### Component Structure

```
app/
├── blueprints/
│   └── auth/
│       ├── __init__.py
│       ├── auth_manager.py      # Authentication engine
│       └── routes.py            # Flask routes and session management
├── config_loader.py             # Configuration management
├── __init__.py                  # App factory with auth initialization
└── templates/
    └── auth/
        └── login.html           # Login form with multi-auth support
```

### Authentication Flow

```
User Request
    │
    ▼
Login Form (login.html)
    │
    ├─► Select Auth Method (local/ldap)
    ├─► Enter Credentials
    └─► Optional: Domain (Windows only)
    │
    ▼
Routes (routes.py)
    │
    ├─► Validate input
    └─► Call auth_manager.authenticate()
    │
    ▼
AuthenticationManager (auth_manager.py)
    │
    ├─► Route to appropriate backend
    │   ├─► Windows (win32security)
    │   ├─► Linux/Unix (PAM)
    │   └─► LDAP (ldap3)
    │
    ▼
AuthResult
    │
    ├─► Success: Create session + redirect to dashboard
    └─► Failure: Show error message
```

---

## Installation

### 1. Install Dependencies

```bash
# Core dependencies
pip install flask flask-socketio pyyaml ldap3 python-dotenv

# Platform-specific authentication
# Windows:
pip install pywin32 WMI

# Linux/Unix:
pip install python-pam
```

### 2. Create Required Files

The authentication system requires these files in your Anguis installation:

**app/config_loader.py** - Configuration management
```python
# Loads config.yaml and applies environment variable overrides
# Provides default values for all settings
```

**app/blueprints/auth/auth_manager.py** - Authentication engine
```python
# Multi-backend authentication manager
# Platform detection and method routing
# Group membership extraction
```

**app/blueprints/auth/routes.py** - Updated routes
```python
# Multi-method login support
# Session management with groups
# API endpoints for auth status
```

**app/__init__.py** - Updated app factory
```python
# Load configuration
# Initialize auth manager
# Register blueprints
```

**app/templates/auth/login.html** - Updated login form
```python
# Auth method selector
# Dynamic domain field for Windows
# Preserves existing Anguis theme
```

**config.yaml** - Configuration file (root directory)
```yaml
# Authentication settings
# Server configuration
# Logging preferences
```

### 3. Directory Structure

After installation, verify this structure:

```
Anguis/
├── app/
│   ├── __init__.py              ← Updated
│   ├── config_loader.py         ← New
│   ├── blueprints/
│   │   └── auth/
│   │       ├── __init__.py
│   │       ├── auth_manager.py  ← New
│   │       └── routes.py        ← Updated
│   └── templates/
│       └── auth/
│           └── login.html       ← Updated
└── config.yaml                  ← New
```

---

## Configuration

### Basic Configuration (config.yaml)

Create `config.yaml` in your Anguis root directory:

```yaml
# Authentication configuration
authentication:
  # Default method: 'local' or 'ldap'
  default_method: "local"
  
  # Local OS authentication
  local:
    enabled: true
    domain_required: false              # Require domain for Windows auth
    use_computer_name_as_domain: true   # Use computer name as default domain
  
  # LDAP/Active Directory
  ldap:
    enabled: false                       # Set true to enable LDAP
    server: "ldap.yourcompany.com"
    port: 389                            # Use 636 for LDAPS
    use_ssl: false                       # Set true for LDAPS
    base_dn: "dc=yourcompany,dc=com"
    user_dn_template: "uid={username},ou=users,dc=yourcompany,dc=com"
    search_groups: false                 # Set true to retrieve groups
    group_base_dn: "ou=groups,dc=yourcompany,dc=com"
    group_filter: "(&(objectClass=group)(member={user_dn}))"

# Flask settings
flask:
  secret_key: null                       # Auto-generated if not set
  session_timeout_minutes: 120           # 2 hours

# Server settings
server:
  host: "0.0.0.0"
  port: 8086
  debug: false

# Logging
logging:
  level: "INFO"
  file: null                             # Set to "logs/Anguis.log" for file logging
```

### Environment Variable Overrides

Environment variables take precedence over config.yaml:

```bash
# Flask configuration
export FLASK_SECRET_KEY="your-secret-key-here"
export SESSION_TIMEOUT_MINUTES=60

# Server configuration
export Anguis_HOST="0.0.0.0"
export Anguis_PORT=8086
export Anguis_DEBUG=false

# Authentication
export AUTH_DEFAULT_METHOD="local"     # or "ldap"

# LDAP settings
export LDAP_ENABLED=true
export LDAP_SERVER="ldap.company.com"
export LDAP_PORT=389
export LDAP_BASE_DN="dc=company,dc=com"
export LDAP_USER_DN_TEMPLATE="uid={username},ou=users,dc=company,dc=com"

# Logging
export LOG_LEVEL="INFO"
export LOG_FILE="logs/Anguis.log"
```

### Active Directory Example

For Active Directory, use this configuration:

```yaml
authentication:
  default_method: "ldap"
  ldap:
    enabled: true
    server: "ad.yourcompany.com"
    port: 389
    use_ssl: false
    base_dn: "dc=yourcompany,dc=com"
    user_dn_template: "{username}@yourcompany.com"  # AD format
    search_groups: true
    group_filter: "(&(objectClass=group)(member=CN={username},OU=Users,DC=yourcompany,DC=com))"
```

---

## Usage

### Starting the Application

```bash
cd app
python run.py

# Access at http://localhost:8086
# Redirects to login page
```

### Login Process

1. **Navigate to** `http://localhost:8086`
2. **Redirected to** login page
3. **Select authentication method** (if multiple available)
4. **Enter credentials:**
   - Username
   - Password
   - Domain (Windows local auth only)
5. **Click Sign In**
6. **On success:** Redirect to dashboard with session created

### Session Data

After successful authentication, the session contains:

```python
session['logged_in'] = True
session['username'] = 'COMPUTERNAME@username'  # or 'username' for Linux/LDAP
session['auth_method'] = 'local'               # or 'ldap'
session['groups'] = ['Users', 'Administrators'] # User's group memberships
```

### Accessing Session Data in Routes

```python
from flask import session
from app.blueprints.auth.routes import login_required

@app.route('/protected')
@login_required
def protected_route():
    username = session.get('username')
    groups = session.get('groups', [])
    auth_method = session.get('auth_method')
    
    return f"Hello {username}! Groups: {groups}"
```

### Logout

```python
# Programmatic logout
session.clear()

# Or redirect to logout route
return redirect(url_for('auth.logout'))
```

---

## Authentication Methods

### Windows Local Authentication

**Requirements:**
- Windows operating system
- `pywin32` package installed
- Valid Windows user account

**How it works:**
1. Uses `win32security.LogonUser()` for authentication
2. Authenticates against Windows domain or local computer
3. Extracts group memberships via `win32net.NetUserGetLocalGroups()`
4. Creates filesystem-safe username: `DOMAIN@username`

**Configuration:**
```yaml
authentication:
  default_method: "local"
  local:
    enabled: true
    domain_required: false              # Set true to require domain
    use_computer_name_as_domain: true   # Use PC name if no domain specified
```

**Login Example:**
- Username: `jdoe`
- Password: `password123`
- Domain: `WORKGROUP` (or leave blank to auto-detect)

**Troubleshooting:**
```bash
# Test pywin32 installation
python -c "import win32security; print('OK')"

# Run post-install script if needed (as Administrator)
python Scripts/pywin32_postinstall.py -install
```

### Linux/Unix PAM Authentication

**Requirements:**
- Linux/Unix operating system
- `python-pam` package installed
- PAM development libraries
- Valid system user account

**How it works:**
1. Uses PAM (Pluggable Authentication Modules)
2. Authenticates against `/etc/passwd` and `/etc/shadow`
3. Extracts group memberships from `/etc/group`
4. Username format: standard Unix username

**Configuration:**
```yaml
authentication:
  default_method: "local"
  local:
    enabled: true
```

**Installation (Ubuntu/Debian):**
```bash
sudo apt-get install libpam0g-dev
pip install python-pam
```

**Login Example:**
- Username: `jdoe`
- Password: `password123`

### LDAP/Active Directory Authentication

**Requirements:**
- LDAP server accessible from Anguis
- `ldap3` package installed
- Valid LDAP credentials
- Proper DN template configuration

**How it works:**
1. Connects to LDAP server
2. Builds user DN from template
3. Attempts bind (authentication)
4. Optionally retrieves group memberships
5. Returns username and groups

**Configuration:**
```yaml
authentication:
  default_method: "ldap"
  ldap:
    enabled: true
    server: "ldap.company.com"
    port: 389
    use_ssl: false
    base_dn: "dc=company,dc=com"
    user_dn_template: "uid={username},ou=users,dc=company,dc=com"
    search_groups: true
    group_base_dn: "ou=groups,dc=company,dc=com"
```

**Login Example:**
- Username: `jdoe`
- Password: `password123`
- Auth Method: LDAP

**Testing LDAP Connection:**
```bash
# Test with ldapsearch
ldapsearch -x -H ldap://ldap.company.com \
  -D "uid=jdoe,ou=users,dc=company,dc=com" \
  -W \
  -b "dc=company,dc=com"
```

---

## Troubleshooting

### Common Issues

**1. "Authentication manager not initialized"**

Check `app/__init__.py` has these lines:

```python
from app.config_loader import load_config
from app.blueprints.auth.routes import init_auth_manager

config = load_config('config.yaml')
auth_config = config.get('authentication', {})
init_auth_manager(auth_config)
```

**2. "No module named 'win32security'"** (Windows)

```bash
pip install pywin32
python Scripts/pywin32_postinstall.py -install
```

**3. "No module named 'pam'"** (Linux)

```bash
sudo apt-get install libpam0g-dev
pip install python-pam
```

**4. "LDAP connection timeout"**

- Verify LDAP server address and port
- Check firewall allows LDAP traffic (port 389/636)
- Test with `ldapsearch` command
- Verify `ldap3` is installed: `pip install ldap3`

**5. Auth method selector not showing**

- Check `auth_info` is passed to template
- Verify multiple auth methods are available
- Check browser console for JavaScript errors

**6. Domain field not appearing (Windows)**

- Ensure system is Windows
- Verify "Local" auth method is selected
- Check template has domain field code

### Debug Mode

Enable detailed logging:

```yaml
# config.yaml
logging:
  level: "DEBUG"
  file: "logs/Anguis.log"
```

Or via environment:
```bash
export LOG_LEVEL=DEBUG
```

View logs:
```bash
tail -f logs/Anguis.log
```

### Testing Authentication

Test the auth manager directly:

```python
from app.auth.auth_manager import AuthenticationManager
from app.config_loader import load_config

config = load_config()
auth_config = config.get('authentication', {})
auth_mgr = AuthenticationManager(auth_config)

# Test authentication
result = auth_mgr.authenticate(
    username='testuser',
    password='testpass',
    auth_method='local'
)

print(f"Success: {result.success}")
if result.success:
    print(f"Username: {result.username}")
    print(f"Groups: {result.groups}")
else:
    print(f"Error: {result.error}")
```

---

## Security Considerations

### Production Deployment

**1. Use Strong Secret Key**

```bash
# Generate secure key
python -c "import secrets; print(secrets.token_hex(32))"

# Set in environment
export FLASK_SECRET_KEY="<generated-key>"
```

**2. Enable HTTPS**

Never use authentication over plain HTTP in production. Configure a reverse proxy:

```nginx
# nginx example
server {
    listen 443 ssl;
    server_name Anguis.yourcompany.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8086;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**3. Use LDAPS for LDAP**

```yaml
ldap:
  use_ssl: true
  port: 636
```

**4. Restrict Session Timeout**

```yaml
flask:
  session_timeout_minutes: 30  # Production: 15-60 minutes
```

**5. Enable Audit Logging**

All authentication attempts are automatically logged:

```
INFO:app.blueprints.auth.routes:User WORKGROUP@jdoe logged in via local
WARNING:app.blueprints.auth.routes:Failed login attempt for admin: Invalid credentials
```

Monitor these logs for suspicious activity.

### Password Security

- **Passwords are never stored** by Anguis
- Authentication is delegated to:
  - Windows: Native Windows authentication API
  - Linux: PAM system authentication
  - LDAP: Direct bind to LDAP server
- Sessions use secure Flask session cookies
- Passwords are not logged

### Rate Limiting

Consider adding rate limiting for production:

```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: request.remote_addr)

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    # ... login logic
```

---

## API Endpoints

### GET /auth/api/auth/methods

Get available authentication methods and system information.

**Response:**
```json
{
  "available_methods": ["local", "ldap"],
  "default_method": "local",
  "system_info": {
    "system": "Windows",
    "windows_auth_available": true,
    "pam_auth_available": false,
    "ldap_available": true,
    "ldap_configured": true
  }
}
```

### POST /auth/api/auth/validate

Validate current session.

**Response (authenticated):**
```json
{
  "valid": true,
  "username": "WORKGROUP@jdoe",
  "auth_method": "local",
  "groups": ["Users", "Administrators"]
}
```

**Response (not authenticated):**
```json
{
  "valid": false
}
```

---

## Migration from Simple Auth

If upgrading from the basic `admin/admin` authentication:

1. **Backup database:**
```bash
cp instance/assets.db instance/assets.db.backup
```

2. **Install new files** as described in Installation section

3. **Create config.yaml** with local auth enabled

4. **Test with local authentication** first before enabling LDAP

5. **Update any hardcoded** `admin/admin` references in code

6. **Restart application:**
```bash
python run.py
```

---

## Summary

The Anguis authentication system provides enterprise-grade authentication with:

- Multiple backend support (Windows, Linux, LDAP)
- Flexible YAML + environment variable configuration
- Automatic platform detection
- Group membership tracking
- Preserved UI/UX (Anguis theme)
- Secure session management
- Comprehensive logging

**Current Status:** ✓ Production ready with local Windows authentication working

For additional support, see the troubleshooting section or check application logs in `logs/Anguis.log`.

---

*Last Updated: 2025-10-04 | Authentication v1.0*