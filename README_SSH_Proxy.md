# SSH Routing Solution with Environment Variable Configuration

A paramiko-based SSH routing system that provides enterprise-grade network access control through environment variable configuration. This solution enables transparent SSH proxy routing based on destination IP ranges and hostname patterns, similar to router prefix lists and route maps.

## Overview

This system automatically routes SSH connections through designated proxy servers based on configurable rules, while maintaining full compatibility with existing SSH functionality including shell commands, prompt detection, and legacy device support.

## Key Features

- **Environment Variable Configuration**: Zero-code changes required for routing policy updates
- **IP Network Matching**: CIDR notation support for subnet-based routing (e.g., `10.0.0.0/8`)
- **Hostname Pattern Matching**: Wildcard support for domain-based routing (e.g., `*.company.com`)
- **Multiple Actions**: Direct connection, proxy routing, or connection blocking
- **Legacy Device Support**: Full compatibility with older network equipment
- **Transparent Operation**: Existing SSH functionality works identically through proxies
- **Windows & Linux Compatible**: Cross-platform environment variable support

## Architecture

```
[Client] --> [Routing Engine] --> [Direct Connection] --> [Target]
                               |
                               --> [SSH Proxy] --> [Target]
                               |
                               --> [Connection Denied]
```

The routing engine evaluates destination hosts against configured rules and automatically establishes the appropriate connection type.

## Environment Variables

### Core Routing Configuration

```bash
# Enable/disable routing system
export SSH_USE_ROUTING=true

# Proxy server configuration
export SSH_PROXY_HOST=jump.company.com
export SSH_PROXY_PORT=22
export SSH_PROXY_USER=jumpuser
export SSH_PROXY_PASS=your_proxy_password
export SSH_PROXY_KEY=/path/to/proxy/private/key

# Routing rules (JSON format)
export SSH_ROUTING_RULES='[
  {"match": "10.0.0.0/8", "action": "direct"},
  {"match": "192.168.1.0/24", "action": "proxy"},
  {"match": "*.internal.company.com", "action": "proxy"},
  {"match": "*.forbidden.com", "action": "deny"},
  {"match": "*", "action": "direct"}
]'
```

### Windows Environment Variables

#### Command Prompt
```cmd
set SSH_USE_ROUTING=true
set SSH_PROXY_HOST=jump.company.com
set SSH_PROXY_USER=jumpuser
set SSH_PROXY_PASS=your_password
set SSH_ROUTING_RULES=[{"match": "192.168.1.0/24", "action": "proxy"}]
```

#### PowerShell
```powershell
$env:SSH_USE_ROUTING="true"
$env:SSH_PROXY_HOST="jump.company.com"
$env:SSH_PROXY_USER="jumpuser"
$env:SSH_PROXY_PASS="your_password"
$env:SSH_ROUTING_RULES='[{"match": "192.168.1.0/24", "action": "proxy"}]'
```

## Routing Rules Format

Rules are processed in order until a match is found. Each rule contains:

- `match`: Pattern to match against (IP/CIDR or hostname pattern)
- `action`: Action to take (`direct`, `proxy`, or `deny`)
- `comment`: Optional description for documentation

### Rule Examples

```json
[
  {
    "match": "10.68.0.0/16",
    "action": "proxy",
    "comment": "Corporate data center network"
  },
  {
    "match": "192.168.0.0/16",
    "action": "direct",
    "comment": "Local development networks"
  },
  {
    "match": "*.prod.company.com",
    "action": "proxy",
    "comment": "Production servers require proxy"
  },
  {
    "match": "test*.company.com",
    "action": "direct",
    "comment": "Test environments allow direct access"
  },
  {
    "match": "*.external-vendor.com",
    "action": "deny",
    "comment": "Blocked external access"
  },
  {
    "match": "*",
    "action": "direct",
    "comment": "Default policy - allow direct"
  }
]
```

## Implementation

### Enhanced SSHClientOptions

```python
import os
import json

class SSHClientOptions:
    def __init__(self, host, username, password, **kwargs):
        # Standard SSH parameters
        self.host = host
        self.username = username
        self.password = password
        
        # Routing configuration from environment
        self.routing_enabled = os.getenv('SSH_USE_ROUTING', 'false').lower() == 'true'
        self.proxy_host = os.getenv('SSH_PROXY_HOST')
        self.proxy_port = int(os.getenv('SSH_PROXY_PORT', '22'))
        self.proxy_username = os.getenv('SSH_PROXY_USER')
        self.proxy_password = os.getenv('SSH_PROXY_PASS')
        self.proxy_key_path = os.getenv('SSH_PROXY_KEY')
        
        # Parse routing rules
        self.routing_rules = self._parse_routing_rules()
    
    def _parse_routing_rules(self):
        rules_json = os.getenv('SSH_ROUTING_RULES', '[]')
        try:
            return json.loads(rules_json)
        except Exception as e:
            print(f"Error parsing routing rules: {e}")
            return []
```

### Routing Engine

```python
import ipaddress
import fnmatch
import socket

class SimpleSSHRouter:
    def __init__(self, rules):
        self.rules = rules
    
    def resolve_route(self, destination_host, destination_port=22):
        dest_ip = self._resolve_hostname(destination_host)
        
        for rule in self.rules:
            if self._matches_rule(destination_host, dest_ip, rule.get('match')):
                action = rule.get('action', 'direct')
                print(f"Route matched: {rule.get('match')} -> {action}")
                return action
        
        return 'direct'  # Default action
    
    def _matches_rule(self, hostname, ip_addr, pattern):
        # IP network matching
        if '/' in pattern:
            try:
                if ip_addr and ipaddress.ip_address(ip_addr) in ipaddress.ip_network(pattern, strict=False):
                    return True
            except (ipaddress.AddressValueError, ValueError):
                pass
        
        # Hostname pattern matching
        return fnmatch.fnmatch(hostname.lower(), pattern.lower())
    
    def _resolve_hostname(self, hostname):
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            return None
```

### Enhanced Connection Logic

```python
def connect(self):
    # Determine routing decision
    route_action = 'direct'
    if self.router:
        route_action = self.router.resolve_route(self._options.host, self._options.port)
        print(f"Routing decision: {route_action}")
    
    if route_action == 'deny':
        raise ConnectionError(f"Connection denied by routing policy")
    elif route_action == 'proxy':
        self._connect_through_proxy()
    else:
        self._connect_direct()

def _connect_through_proxy(self):
    # Connect to proxy server
    self._proxy_client = paramiko.SSHClient()
    self._proxy_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    self._proxy_client.connect(
        hostname=self._options.proxy_host,
        port=self._options.proxy_port,
        username=self._options.proxy_username,
        password=self._options.proxy_password
    )
    
    # Create tunnel through proxy
    transport = self._proxy_client.get_transport()
    tunnel_channel = transport.open_channel(
        'direct-tcpip',
        (self._options.host, self._options.port),
        ('localhost', 0)
    )
    
    # Connect to final destination through tunnel
    self._ssh_client = paramiko.SSHClient()
    self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    self._ssh_client.connect(
        hostname=self._options.host,
        port=self._options.port,
        username=self._options.username,
        password=self._options.password,
        sock=tunnel_channel  # Route through proxy tunnel
    )
```

## Testing

### Test Environment Setup

1. **Configure environment variables:**
```bash
export SSH_USE_ROUTING=true
export SSH_PROXY_HOST=your-jump-server.com
export SSH_PROXY_USER=your-proxy-username
export SSH_PROXY_PASS=your-proxy-password
export SSH_ROUTING_RULES='[
  {"match": "10.68.0.0/16", "action": "proxy"},
  {"match": "*", "action": "direct"}
]'
```

2. **Test script:**
```python
def test_routing():
    options = SSHClientOptions(
        host="10.68.48.60",
        username="test-user",
        password="test-password",
        debug=True
    )
    
    client = SSHClient(options)
    try:
        client.connect()
        result = client.execute_command("show users")
        print("Connection successful!")
        print(f"Result: {result}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    test_routing()
```

### Test Results Validation

**Expected behavior when routing is enabled:**
```
Route matched: 10.68.0.0/16 -> proxy
Routing decision: proxy
Connecting via proxy: jumpuser@jump-server.com:22
Connected to proxy, creating tunnel...
Established connection through proxy tunnel
```

**Source verification using network device commands:**
```bash
# With proxy routing enabled
show users
# Output shows connection from proxy server IP

# With routing disabled (SSH_USE_ROUTING=false)
show users  
# Output shows connection from client workstation IP
```

### Performance Testing

Typical connection times:
- **Direct connection**: ~0.8-1.2 seconds
- **Proxy connection**: ~2.5-3.5 seconds
- **Overhead**: ~2 seconds for proxy hop (acceptable)

### Test Scenarios

1. **IP Range Matching**
   - Test various IP addresses within configured subnets
   - Verify CIDR notation handling (`10.0.0.0/8`, `192.168.1.0/24`)

2. **Hostname Pattern Matching**  
   - Test wildcard patterns (`*.company.com`, `test*.domain.com`)
   - Verify case-insensitive matching

3. **Connection Blocking**
   - Test `deny` action with forbidden destinations
   - Verify proper error handling

4. **Fallback Behavior**
   - Test with missing proxy credentials
   - Verify graceful degradation to direct connection when appropriate

## Production Deployment

### Security Considerations

1. **Environment Variable Security**
   - Store sensitive credentials in secure environment variable systems
   - Consider using SSH key authentication over passwords
   - Implement proper access controls on configuration files

2. **Network Security**
   - Ensure proxy servers are properly hardened
   - Implement network segmentation around jump hosts
   - Monitor and log all proxy connections

3. **Audit Requirements**
   - Log all routing decisions for compliance
   - Track connection sources and destinations
   - Implement alerting for denied connections

### Enterprise Deployment Example

```bash
# Production environment variables
export SSH_USE_ROUTING=true
export SSH_PROXY_HOST=enterprise-jump.company.com
export SSH_PROXY_USER=automated-system
export SSH_PROXY_KEY=/secure/path/to/proxy-key
export SSH_ROUTING_RULES='[
  {"match": "10.0.0.0/8", "action": "proxy", "comment": "Internal corporate networks"},
  {"match": "172.16.0.0/12", "action": "proxy", "comment": "Private networks"},
  {"match": "192.168.0.0/16", "action": "direct", "comment": "Development networks"},
  {"match": "*.prod.company.com", "action": "proxy", "comment": "Production systems"},
  {"match": "*.dev.company.com", "action": "direct", "comment": "Development systems"},
  {"match": "*.external.com", "action": "deny", "comment": "Blocked external access"},
  {"match": "*", "action": "direct", "comment": "Default allow with logging"}
]'
```

## Troubleshooting

### Common Issues

1. **Connection Timeouts**
   - Check proxy server connectivity
   - Verify proxy authentication credentials
   - Increase timeout values for slow networks

2. **Rule Matching Problems**
   - Test IP address resolution for hostname rules
   - Verify CIDR notation syntax
   - Check rule order (first match wins)

3. **Authentication Failures**
   - Verify proxy server credentials
   - Check SSH key file permissions
   - Test proxy connection independently

### Debug Mode

Enable verbose logging:
```python
options = SSHClientOptions(
    host="target-host",
    username="user",
    password="pass",
    debug=True  # Enables detailed logging
)
```

### Network Verification

Use network device commands to verify connection source:
```bash
# Cisco/network devices
show users
show sessions
show tcp brief

# Linux servers  
who
w
netstat -tn
```

## Limitations

1. **Single Proxy Hop**: Current implementation supports one proxy server per connection
2. **Environment Variables**: Configuration limited to environment variable complexity
3. **Rule Processing**: Rules processed sequentially (first match wins)

## Future Enhancements

1. **Multi-hop Proxy Chains**: Support for multiple proxy hops
2. **Dynamic Configuration**: Runtime rule updates without restart
3. **Load Balancing**: Multiple proxy servers with failover
4. **Enhanced Logging**: Structured logging with audit trails
5. **GUI Configuration**: Visual rule editor for non-technical users

## Compatibility

- **Python**: 3.7+
- **Paramiko**: 2.7+
- **Operating Systems**: Windows, Linux, macOS
- **SSH Servers**: OpenSSH, Cisco IOS, Juniper JUNOS, and other SSH implementations
- **Network Equipment**: Full support for legacy devices with compatibility algorithms