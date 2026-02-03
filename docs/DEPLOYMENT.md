# Configuration Deployment System

A robust configuration deployment system for network devices with built-in safety features including automatic backups, dry-run mode, and rollback capability.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Safety Features](#safety-features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Examples](#usage-examples)
- [Command-Line Interface](#command-line-interface)
- [Python API](#python-api)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The Configuration Deployment System provides a safe and efficient way to deploy network device configurations using Jinja2 templates. It integrates with the existing inventory, template engine, and backup systems to provide a comprehensive deployment solution.

## Features

### Core Capabilities

- **Template-Based Configuration**: Deploy configurations using Jinja2 templates
- **Single & Multi-Device Deployment**: Deploy to one device or many simultaneously
- **Parallel Execution**: Deploy to multiple devices in parallel for faster operations
- **Dry-Run Mode**: Preview configurations before actual deployment
- **Automatic Backups**: Create configuration backups before deployment
- **Automatic Rollback**: Restore previous configuration if deployment fails
- **Comprehensive Reporting**: Detailed deployment reports with success/failure statistics

### Safety Features

1. **Pre-Deployment Backup**
   - Automatically backs up current configuration before deployment
   - Can be disabled per deployment if needed
   - Backup files timestamped and stored securely

2. **Dry-Run Mode**
   - Preview rendered configurations without deploying
   - Test template rendering and variable substitution
   - Validate configuration syntax before deployment

3. **Automatic Rollback**
   - If deployment fails, automatically restores previous configuration
   - Uses pre-deployment backup for rollback
   - Logs all rollback attempts

4. **Error Handling**
   - Graceful handling of connection failures
   - Detailed error messages for troubleshooting
   - Continues with remaining devices even if some fail

5. **Deployment Verification**
   - Optional verification that configuration was applied
   - Compares deployed configuration with expected configuration
   - Identifies missing or incorrect configuration lines

## Installation

The deployment system is part of the network automation project. Ensure all dependencies are installed:

```bash
# Install required packages
pip install -r requirements.txt

# Verify installation
python3 -m src.deployment
```

## Quick Start

### 1. List Available Templates

```bash
./deploy_config.py --list-templates
```

### 2. List Available Devices

```bash
./deploy_config.py --list-devices
```

### 3. Preview Deployment (Dry-Run)

```bash
./deploy_config.py \
  --device spine1 \
  --template example_ntp.j2 \
  --var ntp_server=10.0.0.1 \
  --var timezone=UTC \
  --dry-run
```

### 4. Deploy to Single Device

```bash
./deploy_config.py \
  --device spine1 \
  --template example_ntp.j2 \
  --var ntp_server=10.0.0.1 \
  --var timezone=UTC
```

### 5. Deploy to Multiple Devices

```bash
./deploy_config.py \
  --role spine \
  --template example_ntp.j2 \
  --var ntp_server=10.0.0.1 \
  --parallel
```

## Usage Examples

### Example 1: Deploy NTP Configuration

Deploy NTP server configuration to a single device:

```bash
./deploy_config.py \
  --device spine1 \
  --template example_ntp.j2 \
  --var ntp_server=10.0.0.1 \
  --var timezone=UTC
```

Expected output:
```
✓ Deployment manager initialized

================================================================================
DEPLOYMENT CONFIGURATION
================================================================================
  Template:      example_ntp.j2
  Variables:     2 variables
    - ntp_server = 10.0.0.1
    - timezone = UTC
  Dry-run:       False
  Auto-backup:   True
================================================================================

ℹ Starting DEPLOYMENT to device 'spine1'...

✓ Deployment successful to spine1
ℹ Backup saved: configs/backups/spine1_20250203_143022.cfg

================================================================================
CONFIGURATION DEPLOYMENT REPORT
================================================================================
Timestamp:        2025-02-03 14:30:22
Total devices:    1
Successful:       1
Failed:           0
Success rate:     100.0%
Backups created:  1

--------------------------------------------------------------------------------
SUCCESSFUL DEPLOYMENTS
--------------------------------------------------------------------------------
  ✓ spine1          → example_ntp.j2 (backup: spine1_20250203_143022.cfg)

================================================================================
```

### Example 2: Deploy to Multiple Devices by Role

Deploy SNMP configuration to all spine switches in parallel:

```bash
./deploy_config.py \
  --role spine \
  --template example_snmp.j2 \
  --var snmp_community=public \
  --parallel \
  --workers 5
```

### Example 3: Dry-Run with Preview

Preview configuration before deploying:

```bash
./deploy_config.py \
  --device leaf1 \
  --template example_interface.j2 \
  --var interface_name=ethernet-1/1 \
  --var ip_address=192.168.10.1 \
  --var netmask=24 \
  --dry-run
```

Expected output includes rendered configuration preview:
```
================================================================================
CONFIGURATION PREVIEW
================================================================================
! Interface Configuration for leaf1

/interface ethernet-1/1
    admin-state enable
    description "Configured by automation"
    subinterface 0 {
        admin-state enable
        ipv4 {
            address 192.168.10.1/24
        }
    }
================================================================================
```

### Example 4: Deploy Without Automatic Backup

Deploy configuration without creating a backup (not recommended):

```bash
./deploy_config.py \
  --device border1 \
  --template example_ntp.j2 \
  --var ntp_server=10.0.0.1 \
  --no-backup
```

### Example 5: Deploy to All Devices

Deploy configuration to all devices in inventory:

```bash
./deploy_config.py \
  --all \
  --template example_ntp.j2 \
  --var ntp_server=10.0.0.1 \
  --parallel \
  --save-report reports/ntp_deployment.txt
```

### Example 6: Show Device Details

View detailed information about a specific device:

```bash
./deploy_config.py --show-device spine1
```

Expected output:
```
================================================================================
DEVICE DETAILS: spine1
================================================================================
  name                : spine1
  ip                  : 192.168.1.1
  role                : spine
  location            : lab
  device_type         : nokia_sros
  snmp_enabled        : True
================================================================================
```

## Command-Line Interface

### Deployment Target Options

Specify which devices to deploy to (mutually exclusive):

- `--device DEVICE_NAME` - Deploy to specific device
- `--role ROLE` - Deploy to all devices with specified role
- `--all` - Deploy to all devices in inventory

### Template Options

- `--template TEMPLATE_NAME` - Jinja2 template file (required for deployment)
- `--var KEY=VALUE` - Template variable (can be specified multiple times)

Example:
```bash
--var ntp_server=10.0.0.1 --var timezone=UTC --var priority=1
```

### Deployment Options

- `--dry-run` - Preview configuration without deploying
- `--no-backup` - Skip automatic backup before deployment
- `--parallel` - Deploy to multiple devices in parallel
- `--workers N` - Maximum number of parallel workers (default: 5)

### Report Options

- `--save-report FILE` - Save deployment report to specified file

### Information Options

- `--list-templates` - List all available templates
- `--list-devices` - List all devices in inventory
- `--show-device DEVICE_NAME` - Show details for specified device

### Logging Options

- `--log-level LEVEL` - Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--quiet` - Suppress non-essential output

### Full Command Syntax

```bash
./deploy_config.py [TARGET] --template TEMPLATE [OPTIONS]

# Where TARGET is one of:
#   --device NAME      Deploy to specific device
#   --role ROLE        Deploy to devices with role
#   --all              Deploy to all devices
```

## Python API

### Basic Usage

```python
from src.deployment import ConfigDeployment

# Initialize deployment manager
deployer = ConfigDeployment(auto_backup=True)

# Get device from inventory
device = deployer.inventory_loader.get_device_by_name('spine1')

# Define variables
variables = {
    'ntp_server': '10.0.0.1',
    'timezone': 'UTC'
}

# Preview deployment (dry-run)
preview = deployer.preview_deployment(
    device=device,
    template_name='example_ntp.j2',
    variables=variables
)
print(preview)

# Deploy configuration
result = deployer.deploy_to_device(
    device=device,
    template_name='example_ntp.j2',
    variables=variables,
    dry_run=False
)

if result['success']:
    print(f"Deployed successfully to {result['device_name']}")
    if result['backup_created']:
        print(f"Backup: {result['backup_created']}")
else:
    print(f"Deployment failed: {result['error']}")
```

### Multi-Device Deployment

```python
# Get devices by role
devices = deployer.inventory_loader.get_devices_by_role('spine')

# Deploy to multiple devices in parallel
results = deployer.deploy_to_multiple_devices(
    devices=devices,
    template_name='example_ntp.j2',
    variables_list={'ntp_server': '10.0.0.1'},
    dry_run=False,
    parallel=True,
    max_workers=5
)

# Generate report
report = deployer.generate_deployment_report(results)
print(report)
```

### Device-Specific Variables

```python
# Deploy with different variables per device
devices = [spine1, spine2, spine3]
variables_list = [
    {'ntp_server': '10.0.0.1', 'priority': 1},
    {'ntp_server': '10.0.0.2', 'priority': 2},
    {'ntp_server': '10.0.0.3', 'priority': 3}
]

results = deployer.deploy_to_multiple_devices(
    devices=devices,
    template_name='example_ntp.j2',
    variables_list=variables_list,
    parallel=False
)
```

### Result Dictionary Structure

The `deploy_to_device()` method returns a dictionary with:

```python
{
    'success': bool,              # Whether deployment succeeded
    'device_name': str,           # Name of device
    'template_used': str,         # Template file name
    'backup_created': str|None,   # Path to backup file
    'dry_run': bool,              # Whether this was dry-run
    'config_preview': str|None,   # Rendered config (if dry-run)
    'error': str|None,            # Error message (if failed)
    'timestamp': str,             # Timestamp of deployment
    'output': str|None            # Device command output
}
```

## Best Practices

### 1. Always Test with Dry-Run First

Before deploying to production devices, always test with `--dry-run`:

```bash
# Test first
./deploy_config.py --device spine1 --template config.j2 --var key=value --dry-run

# Then deploy
./deploy_config.py --device spine1 --template config.j2 --var key=value
```

### 2. Use Automatic Backups

Keep automatic backups enabled (default) for safety:

```python
# Good - backups enabled
deployer = ConfigDeployment(auto_backup=True)

# Only disable if you have a specific reason
deployer = ConfigDeployment(auto_backup=False)
```

### 3. Validate Templates Before Deployment

Use the template engine to validate syntax:

```python
is_valid, message = deployer.template_engine.validate_template('config.j2')
if not is_valid:
    print(f"Template error: {message}")
```

### 4. Use Parallel Deployment for Large Scale

For deploying to many devices, use parallel execution:

```bash
./deploy_config.py --role leaf --template config.j2 --parallel --workers 10
```

### 5. Save Deployment Reports

Always save reports for audit trails:

```bash
./deploy_config.py \
  --role spine \
  --template config.j2 \
  --save-report reports/deployment_$(date +%Y%m%d_%H%M%S).txt
```

### 6. Test on Non-Production First

Deploy to lab/test devices before production:

```bash
# Test on lab devices first
./deploy_config.py --device lab-spine1 --template config.j2 --var key=value

# Then deploy to production
./deploy_config.py --role spine --template config.j2 --var key=value
```

### 7. Use Descriptive Variables

Make templates reusable with clear variable names:

```jinja2
{# Good - clear variable names #}
/system ntp
    server {{ ntp_primary_server }}
    server {{ ntp_secondary_server }}

{# Avoid - unclear variable names #}
/system ntp
    server {{ server1 }}
    server {{ server2 }}
```

### 8. Monitor Deployment Progress

For large deployments, watch the logs:

```bash
# Terminal 1: Run deployment
./deploy_config.py --all --template config.j2 --parallel

# Terminal 2: Monitor logs
tail -f logs/network_automation.log
```

## Troubleshooting

### Common Issues

#### 1. Template Not Found

**Error**: `Template 'config.j2' not found in configs/templates`

**Solution**: Check template exists and path is correct:
```bash
./deploy_config.py --list-templates
ls -la configs/templates/
```

#### 2. Device Not Found

**Error**: `Device 'spine1' not found in inventory`

**Solution**: Verify device name in inventory:
```bash
./deploy_config.py --list-devices
./deploy_config.py --show-device spine1
```

#### 3. Connection Failure

**Error**: `Connection failed: Device not reachable`

**Solution**: Check network connectivity and credentials:
```bash
# Test connectivity
ping 192.168.1.1

# Verify credentials in inventory
cat inventory/devices.yaml
```

#### 4. Missing Template Variables

**Error**: `Missing required variable: ntp_server`

**Solution**: Provide all required variables:
```bash
# Check required variables
python3 -c "
from src.template_engine import TemplateEngine
engine = TemplateEngine()
vars = engine.get_template_variables('example_ntp.j2')
print('Required variables:', vars)
"

# Then provide them
./deploy_config.py --device spine1 --template example_ntp.j2 \
  --var ntp_server=10.0.0.1 \
  --var timezone=UTC
```

#### 5. Deployment Failed - Rollback

**Error**: `Configuration deployment failed (rolled back successfully)`

**Solution**: Check the error message and fix the configuration:
```bash
# Check logs for details
tail -100 logs/network_automation.log

# Test with dry-run
./deploy_config.py --device spine1 --template config.j2 --dry-run
```

#### 6. Permission Denied

**Error**: `Failed to create backup directory`

**Solution**: Check file permissions:
```bash
# Create directory manually
mkdir -p configs/backups

# Set permissions
chmod 755 configs/backups
```

### Debug Mode

For detailed troubleshooting, enable debug logging:

```bash
./deploy_config.py \
  --device spine1 \
  --template config.j2 \
  --log-level DEBUG
```

### Check Component Status

Verify all components are working:

```bash
# Test inventory
python3 -c "from src.inventory_loader import InventoryLoader; \
  loader = InventoryLoader(); \
  print(f'Devices: {loader.get_device_count()}')"

# Test templates
python3 -c "from src.template_engine import TemplateEngine; \
  engine = TemplateEngine(); \
  print(f'Templates: {len(engine.list_templates())}')"

# Test backup
python3 -c "from src.backup import ConfigBackup; \
  backup = ConfigBackup(); \
  print(f'Backup manager: {backup}')"

# Test deployment
python3 -c "from src.deployment import ConfigDeployment; \
  deployer = ConfigDeployment(); \
  print(f'Deployer: {deployer}')"
```

## Advanced Features

### Custom Validation

Implement custom validation before deployment:

```python
# Validate template variables
is_valid, missing = deployer._validate_template_variables(
    'example_ntp.j2',
    {'hostname': 'spine1', 'ntp_server': '10.0.0.1'}
)

if not is_valid:
    print(f"Missing variables: {missing}")
```

### Verify Deployment

Verify configuration was applied correctly:

```python
result = deployer.deploy_to_device(...)

if result['success']:
    # Verify deployment
    verified = deployer.verify_deployment(
        device,
        result['config_preview']
    )
    if verified:
        print("Configuration verified")
    else:
        print("Configuration verification failed")
```

### Manual Rollback

Manually rollback to a previous backup:

```python
# Get latest backup
backup_file = deployer.backup_manager.get_latest_backup('spine1')

# Rollback
success = deployer.rollback_on_failure(device, backup_file)
```

## Security Considerations

1. **Credentials**: Store credentials securely in inventory file with restricted permissions
2. **Backups**: Backup files may contain sensitive configuration - protect accordingly
3. **Templates**: Review templates for potential security issues before deployment
4. **Audit Trail**: Keep deployment reports for security auditing
5. **Access Control**: Restrict access to deployment tools to authorized personnel

## Performance Tips

1. **Parallel Execution**: Use `--parallel` for deploying to multiple devices
2. **Worker Count**: Adjust `--workers` based on your system resources
3. **Network Latency**: Consider network conditions when setting timeouts
4. **Batch Size**: Deploy to groups of devices rather than all at once for better control

---
