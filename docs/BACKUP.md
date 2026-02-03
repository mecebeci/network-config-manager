# Configuration Backup System

## Overview

The `ConfigBackup` module provides automated configuration backup functionality for network devices. It retrieves device configurations via SSH and saves them with timestamps to enable version tracking and recovery.

## Features

- **Single & Multi-Device Backups** - Backup one device or multiple devices in batch
- **Parallel Execution** - Speed up backups with concurrent connections (configurable workers)
- **Timestamped Storage** - Each backup includes timestamp for version history
- **Backup Verification** - Automatic validation of backup files
- **Role-Based Filtering** - Backup devices by role (spine, leaf, etc.)
- **Progress Tracking** - Visual progress indicators for batch operations
- **Comprehensive Reporting** - Detailed backup reports with statistics
- **Automatic Cleanup** - Retention policy for old backups

## Quick Start

### Installation

```bash
# Install dependencies
pip install netmiko jinja2 pyyaml tabulate tqdm

# Verify installation
python3 -c "from src.backup import ConfigBackup; print('✓ Ready')"
```

### Basic Usage

```python
from src.backup import ConfigBackup

# Initialize backup manager
backup_mgr = ConfigBackup(
    inventory_path="inventory/devices.yaml",
    backup_dir="configs/backups",
    retention_days=30
)

# Backup a single device
device = backup_mgr.inventory_loader.get_device_by_name("spine1")
result = backup_mgr.backup_device(device)

if result['success']:
    print(f"✓ Backup saved: {result['filepath']}")
else:
    print(f"✗ Backup failed: {result['error']}")
```

### Backup All Devices

```python
# Backup all devices in parallel (fast, recommended)
results = backup_mgr.backup_all_devices(parallel=True)

# Generate and display report
report = backup_mgr.generate_backup_report(results)
print(report)
```

### Backup by Role

```python
# Backup all spine switches
spine_results = backup_mgr.backup_devices_by_role("spine", parallel=True)

# Backup all leaf switches
leaf_results = backup_mgr.backup_devices_by_role("leaf", parallel=True)
```

## Common Tasks

### List Backups for a Device

```python
backups = backup_mgr.list_device_backups("spine1")
for backup in backups:
    print(backup)
```

### Get Latest Backup

```python
latest = backup_mgr.get_latest_backup("spine1")
if latest:
    print(f"Latest backup: {latest}")
```

### Verify Backup

```python
if backup_mgr.verify_backup(filepath):
    print("✓ Backup is valid")
else:
    print("✗ Backup verification failed")
```

### Cleanup Old Backups

```python
# Cleanup all backups older than retention period
result = backup_mgr.cleanup_old_backups()

# Cleanup specific device
result = backup_mgr.cleanup_old_backups(device_name="spine1")

# Custom retention (7 days)
result = backup_mgr.cleanup_old_backups(days=7)

print(f"Deleted {result['deleted_count']} files, freed {result['freed_space']/1024/1024:.2f} MB")
```

## Configuration Options

### Initialization Parameters

```python
backup_mgr = ConfigBackup(
    inventory_path="inventory/devices.yaml",  # Device inventory file
    backup_dir="configs/backups",             # Backup storage directory
    retention_days=30                         # Retention policy (days)
)
```

### Parallel vs Sequential Execution

```python
# Parallel execution (fast, recommended for multiple devices)
results = backup_mgr.backup_all_devices(parallel=True)

# Sequential execution (slower, easier debugging)
results = backup_mgr.backup_all_devices(parallel=False)

# Custom worker count for parallel execution
devices = backup_mgr.inventory_loader.get_all_devices()
results = backup_mgr.backup_multiple_devices(
    devices,
    parallel=True,
    max_workers=10  # Adjust based on system resources
)
```

## API Reference

### ConfigBackup Class

#### Methods

##### backup_device()

Backup a single device's configuration.

```python
result = backup_mgr.backup_device(device, verify=True)
```

**Parameters:**
- `device` (dict): Device dictionary with connection details
- `verify` (bool): Whether to verify backup after saving (default: True)

**Returns:** Dictionary with:
- `success` (bool): Whether backup succeeded
- `device_name` (str): Device name
- `filepath` (str | None): Path to backup file
- `timestamp` (str): Timestamp of backup
- `error` (str | None): Error message if failed
- `file_size` (int | None): Backup file size in bytes

##### backup_multiple_devices()

Backup multiple devices with parallel or sequential execution.

```python
results = backup_mgr.backup_multiple_devices(
    devices,
    parallel=True,
    max_workers=5
)
```

**Parameters:**
- `devices` (list): List of device dictionaries
- `parallel` (bool): Use parallel execution (default: True)
- `max_workers` (int): Maximum parallel workers (default: 5)

**Returns:** List of result dictionaries

##### backup_all_devices()

Backup all devices from inventory.

```python
results = backup_mgr.backup_all_devices(parallel=True)
```

**Parameters:**
- `parallel` (bool): Use parallel execution (default: True)

**Returns:** List of result dictionaries

##### backup_devices_by_role()

Backup devices filtered by role.

```python
results = backup_mgr.backup_devices_by_role(role, parallel=True)
```

**Parameters:**
- `role` (str): Device role (e.g., "spine", "leaf", "border")
- `parallel` (bool): Use parallel execution (default: True)

**Returns:** List of result dictionaries

##### get_latest_backup()

Get the most recent backup file for a device.

```python
filepath = backup_mgr.get_latest_backup("spine1")
```

**Returns:** Path to latest backup file, or None if not found

##### list_device_backups()

List all backup files for a device.

```python
backups = backup_mgr.list_device_backups("spine1")
```

**Returns:** List of backup file paths sorted by date (newest first)

##### verify_backup()

Verify that a backup file is valid.

```python
is_valid = backup_mgr.verify_backup(filepath)
```

**Returns:** True if backup is valid, False otherwise

##### generate_backup_report()

Generate a summary report from backup results.

```python
report = backup_mgr.generate_backup_report(results)
print(report)
```

**Returns:** Formatted report string with statistics

##### cleanup_old_backups()

Remove backup files older than retention period.

```python
# Cleanup all old backups
result = backup_mgr.cleanup_old_backups()

# Cleanup for specific device
result = backup_mgr.cleanup_old_backups(device_name="spine1")

# Cleanup with custom retention
result = backup_mgr.cleanup_old_backups(days=7)
```

**Returns:** Dictionary with cleanup statistics:
- `deleted_count`: Number of files deleted
- `deleted_files`: List of deleted file paths
- `freed_space`: Space freed in bytes
- `errors`: List of error messages

## Backup File Format

### Filename Convention

```
{device_name}_{YYYYMMDD_HHMMSS}.cfg
```

**Examples:**
- `spine1_20250203_143022.cfg`
- `leaf1_20250203_143045.cfg`

### File Contents

Each backup file includes:

1. **Metadata Header** - Device info, timestamp, IP address, device type
2. **Configuration** - Full device configuration

```
# Configuration Backup
# Device: spine1
# IP: 192.168.1.1
# Timestamp: 2025-02-03 14:30:22
# Device Type: nokia_sros
#
# ======================================================================

[Device configuration content here...]
```

## Examples

### Example 1: Daily Backup Script

```python
#!/usr/bin/env python3
"""Daily backup script for all network devices."""

from src.backup import ConfigBackup
from src.utils import setup_logging, print_success, print_error

# Setup logging
logger = setup_logging(log_level="INFO", log_file="logs/daily_backup.log")

# Initialize backup manager
backup_mgr = ConfigBackup(
    inventory_path="inventory/devices.yaml",
    backup_dir="configs/backups",
    retention_days=30
)

# Backup all devices
logger.info("Starting daily backup")
results = backup_mgr.backup_all_devices(parallel=True)

# Generate report
report = backup_mgr.generate_backup_report(results)
print(report)

# Cleanup old backups
cleanup = backup_mgr.cleanup_old_backups()
logger.info(f"Cleanup: deleted {cleanup['deleted_count']} old backups")

# Check for failures
failed = [r for r in results if not r['success']]
if failed:
    print_error(f"Backup completed with {len(failed)} failures")
    for f in failed:
        logger.error(f"Failed: {f['device_name']} - {f['error']}")
else:
    print_success("All backups completed successfully")
```

### Example 2: Pre-Change Backup

```python
"""Backup devices before making configuration changes."""

from src.backup import ConfigBackup

backup_mgr = ConfigBackup(backup_dir="configs/pre_change_backups")

# Backup specific devices that will be changed
devices_to_change = ["spine1", "spine2", "leaf1"]

for device_name in devices_to_change:
    device = backup_mgr.inventory_loader.get_device_by_name(device_name)
    if device:
        result = backup_mgr.backup_device(device)
        if result['success']:
            print(f"✓ Pre-change backup: {device_name}")
        else:
            print(f"✗ Backup failed for {device_name}")
            print("WARNING: Proceeding without backup!")
```

### Example 3: Backup with Email Notification

```python
from src.backup import ConfigBackup
import smtplib
from email.mime.text import MIMEText

backup_mgr = ConfigBackup()

# Perform backup
results = backup_mgr.backup_all_devices()
report = backup_mgr.generate_backup_report(results)

# Send email report
msg = MIMEText(report)
msg['Subject'] = 'Network Device Backup Report'
msg['From'] = 'backup@example.com'
msg['To'] = 'admin@example.com'

s = smtplib.SMTP('localhost')
s.send_message(msg)
s.quit()
```

### Example 4: Scheduled Backups with Cron

```bash
# Add to crontab: Daily backup at 2 AM
0 2 * * * cd /path/to/project && python3 scripts/daily_backup.py

# Weekly cleanup at 3 AM on Sundays
0 3 * * 0 cd /path/to/project && python3 -c "from src.backup import ConfigBackup; ConfigBackup().cleanup_old_backups()"
```

## Device Type Support

### SR Linux (Nokia SROS)

For SR Linux devices, the system uses:
- **Primary command**: `info flat`
- **Fallback command**: `admin show configuration`

The configuration is retrieved in flat format for easier parsing and version control.

### Other Device Types

The system can be extended to support other device types by modifying the `_get_device_config()` method in `src/backup.py`.

## Error Handling

The backup system handles various error scenarios gracefully:

- **Connection Failures** - Logs error, returns failure status, continues with other devices
- **Authentication Errors** - Logs error, returns failure status with clear message
- **Timeout Errors** - Retries with exponential backoff (via ConnectionManager)
- **Command Execution Errors** - Logs error, returns failure status
- **File Write Errors** - Logs error, returns failure status

### Error Handling Example

```python
result = backup_mgr.backup_device(device)

if not result['success']:
    error = result.get('error', 'Unknown error')

    if 'Authentication' in error:
        print(f"Check credentials for {result['device_name']}")
    elif 'not reachable' in error:
        print(f"Check connectivity to {result['device_name']}")
    elif 'timeout' in error.lower():
        print(f"Connection timeout for {result['device_name']}")
    else:
        print(f"Error: {error}")
```

## Best Practices

1. **Regular Backups** - Schedule automated backups (e.g., daily via cron)
2. **Pre-Change Backups** - Always backup before configuration changes
3. **Verify Backups** - Enable verification to ensure backup integrity
4. **Monitor Failures** - Review backup reports for failed devices
5. **Retention Policy** - Set appropriate retention period (30 days recommended)
6. **Parallel Execution** - Use parallel mode for large inventories
7. **Error Handling** - Always check backup results before proceeding with changes
8. **Version Control** - Consider committing backups to Git for change tracking
9. **Storage Management** - Monitor backup directory size, use cleanup regularly
10. **Test Restores** - Periodically test backup restoration procedures

## Logging

The backup system provides comprehensive logging:

- **INFO level**: Backup operations, success/failure status
- **DEBUG level**: Detailed connection info, command execution, file operations
- **ERROR level**: Connection failures, command errors, file write errors

Configure logging:

```python
from src.utils import setup_logging

logger = setup_logging(
    log_level="DEBUG",  # DEBUG, INFO, WARNING, ERROR
    log_file="logs/backup.log"
)
```

Logs are written to:
- **Console**: INFO and above
- **File**: All levels (DEBUG and above)

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: netmiko` | Run `pip install netmiko` or `pip install -r requirements.txt` |
| Connection timeout | Check device IP, network connectivity, firewall rules |
| Authentication failed | Verify credentials in inventory file, check device access permissions |
| Backup file empty or small | Check device type configuration, verify command compatibility, check device permissions |
| Permission denied | Check file system permissions for backup_dir |
| Parallel backups slow | Increase `max_workers` parameter, check network bandwidth, consider sequential mode for debugging |

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
from src.utils import setup_logging

logger = setup_logging(log_level="DEBUG", log_file="logs/backup_debug.log")

# Then use ConfigBackup normally
backup_mgr = ConfigBackup()
```

### Test Backup System

```bash
# Test module import
python3 -c "from src.backup import ConfigBackup; print('✓ Module OK')"

# Test backup on single device
python3 -c "
from src.backup import ConfigBackup
backup_mgr = ConfigBackup()
device = backup_mgr.inventory_loader.get_device_by_name('spine1')
if device:
    result = backup_mgr.backup_device(device)
    print(f'Success: {result[\"success\"]}')
"
```

## Integration with Other Systems

The backup system integrates seamlessly with:

- **Version Control** - Commit backups to Git for change tracking
- **Monitoring** - Parse backup reports for metrics and alerting
- **Configuration Management** - Use backups as baseline configurations
- **Disaster Recovery** - Automate configuration restoration from backups
- **Deployment System** - Pre-deployment backups (see [DEPLOYMENT.md](DEPLOYMENT.md))

### Git Integration Example

```python
from src.backup import ConfigBackup
import subprocess

backup_mgr = ConfigBackup()

# Backup all devices
results = backup_mgr.backup_all_devices(parallel=True)

# Commit to Git if backups successful
success_count = sum(1 for r in results if r['success'])
if success_count > 0:
    subprocess.run(['git', 'add', 'configs/backups/'])
    subprocess.run([
        'git', 'commit', '-m',
        f'Automated backup: {success_count} devices'
    ])
```

## File Structure

```
project/
├── src/
│   └── backup.py                    # Core backup module
├── configs/
│   └── backups/                     # Backup storage
│       ├── spine1_20250203_143022.cfg
│       ├── spine2_20250203_143025.cfg
│       └── ...
├── docs/
│   └── BACKUP.md                   # This documentation
├── inventory/
│   └── devices.yaml                # Device inventory
└── logs/                           # Log files
```

## Performance Tips

1. **Parallel Execution** - Use `parallel=True` for multiple devices
2. **Worker Count** - Adjust `max_workers` based on system resources (CPU, network)
3. **Network Bandwidth** - Consider network capacity when setting worker count
4. **Sequential Mode** - Use for debugging or when parallel causes issues
5. **Backup Frequency** - Balance between safety and storage/network load

---

**Module**: `src.backup.ConfigBackup`
**Size**: 40 KB
**Dependencies**: netmiko, jinja2, pyyaml, tabulate, tqdm
