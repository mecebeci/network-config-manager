# Network Configuration Templates

This directory contains Jinja2 templates for generating network device configurations. These templates are used by the Template Engine to create dynamic, device-specific configurations for SR Linux devices.

## Table of Contents

- [Overview](#overview)
- [Template Format and Syntax](#template-format-and-syntax)
- [Available Templates](#available-templates)
- [Template Variables](#template-variables)
- [Creating New Templates](#creating-new-templates)
- [SR Linux Configuration Syntax](#sr-linux-configuration-syntax)
- [Best Practices](#best-practices)
- [Examples](#examples)

---

## Overview

Templates use Jinja2 syntax to enable dynamic configuration generation. Each template can include:

- **Variables**: Placeholders that get replaced with actual values (e.g., `{{ hostname }}`)
- **Conditionals**: Logic to include/exclude sections based on conditions (e.g., `{% if ip_address %}`)
- **Loops**: Iterate over lists of items (e.g., `{% for vlan in vlans %}`)
- **Filters**: Transform variables (e.g., `{{ description | default('N/A') }}`)
- **Comments**: Documentation within templates (e.g., `{# This is a comment #}`)

---

## Template Format and Syntax

### Basic Variable Substitution

```jinja2
hostname {{ hostname }}
ip address {{ ip_address }}
```

### Conditional Blocks

```jinja2
{% if ntp_server %}
/system ntp
    server {{ ntp_server }}
{% endif %}
```

### Default Values

```jinja2
description "{{ description | default('Configured by automation') }}"
timezone {{ timezone | default('UTC') }}
```

### Loops

```jinja2
{% for server in ntp_servers %}
    server {{ server }} {
        admin-state enable
    }
{% endfor %}
```

### Comments

```jinja2
{# This is a comment that won't appear in the rendered output #}
! This is an SR Linux comment that will appear in the output
```

---

## Available Templates

### 1. example_ntp.j2

**Purpose**: Configure NTP server settings

**Required Variables**:
- `hostname` - Device hostname
- `ntp_server` - NTP server IP address

**Optional Variables**:
- `timestamp` - Generation timestamp (auto-added if not provided)

**Usage**:
```python
variables = {
    'hostname': 'spine1',
    'ntp_server': '10.0.0.1'
}
config = engine.render_template('example_ntp.j2', variables)
```

**Output Example**:
```
! NTP Configuration for spine1
! Generated: 2025-02-03 10:30:00

/system ntp
    admin-state enable
    server 10.0.0.1 {
        admin-state enable
        prefer true
    }
```

---

### 2. example_snmp.j2

**Purpose**: Configure SNMP community and network instance

**Required Variables**:
- `hostname` - Device hostname
- `snmp_community` - SNMP community string (e.g., "public")

**Optional Variables**:
- None

**Usage**:
```python
variables = {
    'hostname': 'leaf1',
    'snmp_community': 'public'
}
config = engine.render_template('example_snmp.j2', variables)
```

**Output Example**:
```
! SNMP Configuration for leaf1

/system snmp
    admin-state enable
    network-instance mgmt {
        admin-state enable
    }
    community public {
        authorization ro
    }
```

---

### 3. example_interface.j2

**Purpose**: Configure network interface with IP addressing

**Required Variables**:
- `hostname` - Device hostname
- `interface_name` - Interface name (e.g., "ethernet-1/1")

**Optional Variables**:
- `description` - Interface description (default: "Configured by automation")
- `subinterface_id` - Subinterface ID (default: 0)
- `ip_address` - IPv4 address (optional, won't configure IP if omitted)
- `netmask` - Network prefix length (default: 24)

**Usage**:
```python
variables = {
    'hostname': 'spine1',
    'interface_name': 'ethernet-1/1',
    'description': 'Uplink to leaf1',
    'ip_address': '10.0.1.1',
    'netmask': 30
}
config = engine.render_template('example_interface.j2', variables)
```

**Output Example**:
```
! Interface Configuration for spine1

/interface ethernet-1/1
    admin-state enable
    description "Uplink to leaf1"
    subinterface 0 {
        admin-state enable
        ipv4 {
            address 10.0.1.1/30
        }
    }
```

---

## Template Variables

### Common Variables

These variables are commonly used across templates:

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `hostname` | string | Device hostname | `"spine1"` |
| `ip_address` | string | IPv4 address | `"192.168.1.1"` |
| `timestamp` | string | Generation timestamp | `"2025-02-03 10:30:00"` (auto-added) |
| `role` | string | Device role | `"spine"`, `"leaf"` |
| `device_type` | string | Device type | `"sr_linux"` |

### Device-Specific Variables

You can pass any custom variables from device inventory:

```python
# From inventory
device = {
    'name': 'spine1',
    'ip': '192.168.1.1',
    'role': 'spine',
    'device_type': 'sr_linux',
    'rack': 'A1',
    'site': 'DC1'
}

# Use in template
# Location: {{ site }} / Rack {{ rack }}
```

---

## Creating New Templates

### Step 1: Create Template File

Create a new `.j2` file in this directory:

```bash
configs/templates/my_config.j2
```

### Step 2: Define Template Content

Use Jinja2 syntax with SR Linux configuration commands:

```jinja2
! {{ description | default('Custom Configuration') }}
! Device: {{ hostname }}
! Generated: {{ timestamp }}

/system
    name {{ hostname }}
    {% if location %}
    location "{{ location }}"
    {% endif %}

{% if dns_servers %}
    dns
    {% for dns in dns_servers %}
        server-address {{ dns }}
    {% endfor %}
{% endif %}
```

### Step 3: Document Required Variables

Add a comment block at the top of your template:

```jinja2
{#
Template: my_config.j2
Purpose: System configuration with DNS

Required Variables:
- hostname: Device hostname

Optional Variables:
- location: Physical location
- dns_servers: List of DNS server IPs
- description: Configuration description
#}
```

### Step 4: Test Template

```python
from template_engine import TemplateEngine

engine = TemplateEngine()

# Validate syntax
is_valid, message = engine.validate_template('my_config.j2')
print(f"Valid: {is_valid} - {message}")

# Check required variables
variables = engine.get_template_variables('my_config.j2')
print(f"Variables: {variables}")

# Test render
test_vars = {
    'hostname': 'test-device',
    'location': 'DC1',
    'dns_servers': ['8.8.8.8', '8.8.4.4']
}
config = engine.render_template('my_config.j2', test_vars)
print(config)
```

---

## SR Linux Configuration Syntax

### Configuration Hierarchy

SR Linux uses a hierarchical configuration structure:

```
/system
    name router1
    /ntp
        admin-state enable
        server 10.0.0.1
    /snmp
        admin-state enable
```

### Key Syntax Elements

1. **Path-based configuration**: Use `/` to navigate hierarchy
2. **Indentation**: Use spaces (4 spaces recommended)
3. **Braces for blocks**: Use `{}` for configuration blocks
4. **Comments**: Use `!` for single-line comments

### Common Configuration Paths

| Path | Purpose |
|------|---------|
| `/system` | System-wide settings (hostname, NTP, DNS, etc.) |
| `/interface` | Interface configuration |
| `/network-instance` | VRFs and routing instances |
| `/routing-policy` | Routing policies |
| `/tunnel-interface` | Tunnel interfaces |

### Example SR Linux Configuration

```
! System configuration
/system
    name spine1
    location "DC1-Rack-A1"

! NTP configuration
/system ntp
    admin-state enable
    server 10.0.0.1 {
        admin-state enable
        prefer true
    }

! Interface configuration
/interface ethernet-1/1
    admin-state enable
    description "Uplink"
    subinterface 0 {
        ipv4 {
            address 10.0.1.1/30
        }
    }
```

---

## Best Practices

### 1. Use Descriptive Variable Names

```jinja2
# Good
{{ management_ip_address }}
{{ bgp_peer_as_number }}

# Avoid
{{ ip }}
{{ asn }}
```

### 2. Provide Default Values

```jinja2
description "{{ description | default('Managed by automation') }}"
mtu {{ mtu | default(9000) }}
```

### 3. Add Comments and Documentation

```jinja2
! NTP Configuration
! Server: {{ ntp_server }}
! Updated: {{ timestamp }}
```

### 4. Use Conditionals for Optional Features

```jinja2
{% if enable_snmp %}
/system snmp
    admin-state enable
    community {{ snmp_community }}
{% endif %}
```

### 5. Keep Templates Modular

Create separate templates for different configuration aspects:
- `ntp.j2` - NTP configuration only
- `snmp.j2` - SNMP configuration only
- `interfaces.j2` - Interface configuration only

Then combine them as needed.

### 6. Validate Before Deployment

Always validate templates before using them in production:

```python
# Validate syntax
is_valid, msg = engine.validate_template('my_template.j2')

# Preview output
preview = engine.preview_template('my_template.j2', variables)

# Check for required variables
required_vars = engine.get_template_variables('my_template.j2')
```

### 7. Use Whitespace Control

Jinja2 environment is configured with:
- `trim_blocks=True` - Remove first newline after block
- `lstrip_blocks=True` - Strip leading whitespace from blocks
- `keep_trailing_newline=True` - Preserve file trailing newline

This makes templates cleaner:

```jinja2
{% if condition %}
    configuration here
{% endif %}
```

### 8. Handle Lists and Loops Safely

```jinja2
{% if ntp_servers %}
{% for server in ntp_servers %}
    server {{ server }} {
        admin-state enable
    }
{% endfor %}
{% endif %}
```

### 9. Use Filters for Data Transformation

```jinja2
hostname {{ hostname | upper }}
description "{{ description | default('N/A') | truncate(64) }}"
vlan {{ vlan_id | int }}
```

### 10. Test with Real Data

Always test templates with realistic device data:

```python
# Test with actual device from inventory
device = inventory.get_device('spine1')
config = engine.render_template('full_config.j2', device)
```

---

## Examples

### Complete Configuration Example

**Template: full_device_config.j2**

```jinja2
{#
Full device configuration template
Combines system, NTP, SNMP, and interface settings
#}

! ============================================================================
! Device Configuration: {{ hostname }}
! Role: {{ role | default('unknown') }}
! Generated: {{ timestamp }}
! ============================================================================

! System Configuration
/system
    name {{ hostname }}
    {% if location %}
    location "{{ location }}"
    {% endif %}

! NTP Configuration
{% if ntp_servers %}
/system ntp
    admin-state enable
    {% for server in ntp_servers %}
    server {{ server }} {
        admin-state enable
        {% if loop.first %}
        prefer true
        {% endif %}
    }
    {% endfor %}
{% endif %}

! SNMP Configuration
{% if snmp_community %}
/system snmp
    admin-state enable
    network-instance mgmt {
        admin-state enable
    }
    community {{ snmp_community }} {
        authorization ro
    }
{% endif %}

! Interface Configuration
{% if interfaces %}
{% for interface in interfaces %}
/interface {{ interface.name }}
    admin-state enable
    {% if interface.description %}
    description "{{ interface.description }}"
    {% endif %}
    {% if interface.mtu %}
    mtu {{ interface.mtu }}
    {% endif %}
    subinterface {{ interface.subif | default(0) }} {
        admin-state enable
        {% if interface.ip %}
        ipv4 {
            address {{ interface.ip }}/{{ interface.prefix | default(24) }}
        }
        {% endif %}
    }
{% endfor %}
{% endif %}

! ============================================================================
! End of Configuration
! ============================================================================
```

**Usage:**

```python
from template_engine import TemplateEngine

engine = TemplateEngine()

# Complex device configuration
device_config = {
    'hostname': 'spine1',
    'role': 'spine',
    'location': 'DC1-Row1-Rack5',
    'ntp_servers': ['10.0.0.1', '10.0.0.2'],
    'snmp_community': 'public',
    'interfaces': [
        {
            'name': 'ethernet-1/1',
            'description': 'Uplink to leaf1',
            'mtu': 9000,
            'ip': '10.0.1.1',
            'prefix': 30
        },
        {
            'name': 'ethernet-1/2',
            'description': 'Uplink to leaf2',
            'mtu': 9000,
            'ip': '10.0.1.5',
            'prefix': 30
        },
        {
            'name': 'mgmt0',
            'description': 'Management',
            'ip': '192.168.100.1',
            'prefix': 24,
            'subif': 0
        }
    ]
}

# Render configuration
config = engine.render_template('full_device_config.j2', device_config)

# Save to file
with open(f'configs/{device_config["hostname"]}.cfg', 'w') as f:
    f.write(config)
```

---

