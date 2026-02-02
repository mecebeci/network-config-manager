# Network Device Inventory System

## Purpose

This inventory system serves as the **single source of truth** for all network devices in the lab environment. It provides a centralized, YAML-based configuration that defines device properties, connection parameters, and operational metadata used by all automation scripts.

## Features

- Centralized device management
- Global settings for default connection parameters
- Consistent device metadata across all automation tools
- Easy filtering by role, location, or custom attributes
- SNMP configuration management
- Extensible structure for adding new device properties

## File Structure

### `devices.yaml`

The main inventory file contains two primary sections:

#### 1. Settings Section

Global configuration parameters that apply to all devices unless overridden at the device level.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `default_username` | string | Default SSH/API username | `admin` |
| `default_password` | string | Default SSH/API password | `NokiaSrl1!` |
| `default_device_type` | string | Netmiko device type identifier | `nokia_sros` |
| `connection_timeout` | integer | Connection timeout in seconds | `10` |
| `snmp_community` | string | SNMP community string | `public` |
| `snmp_port` | integer | SNMP port number | `161` |
| `snmp_version` | integer | SNMP protocol version (1, 2, or 3) | `2` |

**Environment Variable Override:**
- `NETWORK_USERNAME` - Overrides `default_username`
- `NETWORK_PASSWORD` - Overrides `default_password`

#### 2. Devices Section

A list of all network devices with their specific properties.

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | Yes | string | Unique device hostname/identifier |
| `ip` | Yes | string | Management IP address |
| `role` | Yes | string | Device role (spine, leaf, border, etc.) |
| `location` | Yes | string | Physical or logical location |
| `device_type` | Yes | string | Device type for connection libraries |
| `snmp_enabled` | Yes | boolean | Whether SNMP is enabled on device |
| `description` | No | string | Human-readable device description |
| `vendor` | No | string | Device manufacturer |
| `model` | No | string | Device model number |
| `tier` | No | string | Network tier (core, access, etc.) |

## Device Entry Examples

### Minimal Device Entry

```yaml
devices:
  - name: switch1
    ip: 192.168.1.10
    role: access
    location: datacenter-1
    device_type: cisco_ios
    snmp_enabled: true
```

### Full Device Entry

```yaml
devices:
  - name: spine1
    ip: 172.21.20.11
    role: spine
    location: lab
    device_type: nokia_sros
    snmp_enabled: true
    description: "Spine switch 1 - Core layer"
    vendor: Nokia
    model: "SR Linux IXR-D3L"
    tier: core
```

### Device with SNMP Disabled

```yaml
devices:
  - name: legacy-switch
    ip: 10.0.0.50
    role: leaf
    location: remote-site
    device_type: cisco_ios
    snmp_enabled: false
    description: "Legacy switch without SNMP support"
```

## How to Add New Devices

1. Open `inventory/devices.yaml`
2. Add a new device entry under the `devices:` section
3. Ensure all required fields are populated:
   - `name` (must be unique)
   - `ip` (must be valid IPv4 address)
   - `role`
   - `location`
   - `device_type`
   - `snmp_enabled`
4. Save the file
5. Validate the inventory using the `InventoryLoader` class:

```python
from src.inventory_loader import InventoryLoader

loader = InventoryLoader()
loader.validate_inventory()  # Raises ValueError if invalid
```

## How to Filter Devices

The `InventoryLoader` class provides several filtering methods:

### Get All Devices

```python
from src.inventory_loader import InventoryLoader

loader = InventoryLoader()
all_devices = loader.get_all_devices()
```

### Get Device by Name

```python
device = loader.get_device_by_name("spine1")
if device:
    print(f"Found device: {device['ip']}")
```

### Get Devices by Role

```python
# Get all spine switches
spine_devices = loader.get_devices_by_role("spine")

# Get all leaf switches
leaf_devices = loader.get_devices_by_role("leaf")
```

### Get Global Settings

```python
settings = loader.get_settings()
print(f"Default username: {settings['default_username']}")
```

### Custom Filtering (Python)

```python
# Filter by location
lab_devices = [d for d in loader.get_all_devices() if d['location'] == 'lab']

# Filter by SNMP enabled
snmp_devices = [d for d in loader.get_all_devices() if d.get('snmp_enabled', False)]

# Filter by vendor
nokia_devices = [d for d in loader.get_all_devices() if d.get('vendor') == 'Nokia']

# Filter by tier
core_devices = [d for d in loader.get_all_devices() if d.get('tier') == 'core']
```

## Best Practices

### 1. Keep IP Addresses Updated

Always ensure management IP addresses match the actual network topology. Cross-reference with:
- `lab/topology.yaml` for Containerlab environments
- Network documentation for production environments

### 2. Use Consistent Naming Conventions

- Device names should be lowercase
- Use descriptive names that indicate role and position (e.g., `spine1`, `leaf2`, `border-router-1`)
- Avoid special characters except hyphens

### 3. Maintain Accurate Roles

Standard roles in spine-leaf architecture:
- `spine` - Core layer switches
- `leaf` - Access layer switches
- `border` - Edge/border devices
- `superspine` - For large-scale fabrics

### 4. Document Device Descriptions

Add meaningful descriptions that help identify device purpose and location:
```yaml
description: "Leaf switch 1 - Access layer - Rack A12"
```

### 5. Keep Credentials Secure

- Never commit actual production passwords to version control
- Use environment variables for sensitive data
- Consider using secret management tools for production

### 6. Validate After Changes

Always validate the inventory after making changes:

```bash
python -c "from src.inventory_loader import InventoryLoader; InventoryLoader().validate_inventory(); print('Inventory is valid!')"
```

### 7. Use Version Control

- Commit inventory changes with descriptive messages
- Review diffs before committing to catch errors
- Tag releases when deploying to production

## Device Type Reference

Common device types for Netmiko:

| Vendor | Device Type String |
|--------|-------------------|
| Nokia SR Linux | `nokia_sros` |
| Cisco IOS | `cisco_ios` |
| Cisco IOS-XE | `cisco_xe` |
| Cisco NX-OS | `cisco_nxos` |
| Arista EOS | `arista_eos` |
| Juniper Junos | `juniper_junos` |

See [Netmiko documentation](https://github.com/ktbyers/netmiko#supported-platforms) for complete list.

## Integration with Automation Scripts

The inventory system integrates with:

- **Connection Managers** - Provides device credentials and types
- **SNMP Collectors** - Supplies SNMP-enabled devices and community strings
- **Configuration Management** - Identifies devices for bulk configuration
- **Monitoring Tools** - Defines devices to monitor
- **Reporting Scripts** - Sources device metadata for reports

## Troubleshooting

### Common Issues

**Issue:** `FileNotFoundError` when loading inventory

**Solution:** Ensure you're running scripts from the project root directory, or provide the full path:

```python
loader = InventoryLoader(inventory_path="path/to/inventory/devices.yaml")
```

**Issue:** Validation fails with duplicate name/IP error

**Solution:** Check for duplicate entries in the devices list and ensure each device has a unique name and IP address.

**Issue:** Device connection fails despite correct inventory

**Solution:** Verify:
1. Device IP is reachable (`ping <ip>`)
2. Credentials are correct
3. Device type matches the actual device platform
4. Firewall/security rules allow connections

## Schema Reference

```yaml
settings:
  default_username: string
  default_password: string
  default_device_type: string
  connection_timeout: integer
  snmp_community: string
  snmp_port: integer
  snmp_version: integer

devices:
  - name: string (required, unique)
    ip: string (required, unique, valid IPv4)
    role: string (required)
    location: string (required)
    device_type: string (required)
    snmp_enabled: boolean (required)
    description: string (optional)
    vendor: string (optional)
    model: string (optional)
    tier: string (optional)
    # ... additional custom fields as needed
```

## Future Enhancements

Planned features for the inventory system:

- Support for device groups/tags
- IPv6 address support
- SNMPv3 authentication parameters
- API endpoint configuration
- Custom port configuration per device
- Device dependency mapping
- Automated discovery and inventory updates
