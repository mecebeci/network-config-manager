# Configuration Backup - Quick Reference

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
cd src && python3 -c "from backup import ConfigBackup; print('✓ Ready')"
```

## Basic Usage

### Single Device Backup

```python
from src.backup import ConfigBackup

# Initialize
backup_mgr = ConfigBackup()

# Backup one device
device = backup_mgr.inventory_loader.get_device_by_name("spine1")
result = backup_mgr.backup_device(device)

print(f"Success: {result['success']}")
print(f"File: {result['filepath']}")
```

### Backup All Devices (Parallel)

```python
backup_mgr = ConfigBackup()

# Fast parallel backup
results = backup_mgr.backup_all_devices(parallel=True)

# Show report
print(backup_mgr.generate_backup_report(results))
```

### Backup by Role

```python
backup_mgr = ConfigBackup()

# Backup all spine switches
results = backup_mgr.backup_devices_by_role("spine")

# Backup all leaf switches
results = backup_mgr.backup_devices_by_role("leaf")
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
```

### Cleanup Old Backups

```python
# Cleanup all backups older than retention period
result = backup_mgr.cleanup_old_backups()

# Cleanup specific device
result = backup_mgr.cleanup_old_backups(device_name="spine1")

# Custom retention (7 days)
result = backup_mgr.cleanup_old_backups(days=7)

print(f"Deleted {result['deleted_count']} files")
```

## Configuration Options

```python
backup_mgr = ConfigBackup(
    inventory_path="inventory/devices.yaml",  # Device inventory
    backup_dir="configs/backups",             # Backup storage
    retention_days=30                         # Retention policy
)
```

## Parallel vs Sequential

```python
# Parallel (fast, recommended)
results = backup_mgr.backup_all_devices(parallel=True)

# Sequential (slower, easier debugging)
results = backup_mgr.backup_all_devices(parallel=False)

# Custom worker count
devices = backup_mgr.inventory_loader.get_all_devices()
results = backup_mgr.backup_multiple_devices(
    devices,
    parallel=True,
    max_workers=10
)
```

## Result Dictionary Format

```python
result = {
    'success': True,                    # Boolean status
    'device_name': 'spine1',           # Device name
    'filepath': 'configs/backups/...',  # Backup file path
    'timestamp': '2025-02-03 14:30:22', # Human-readable time
    'error': None,                      # Error message or None
    'file_size': 12345                 # File size in bytes
}
```

## Backup Filename Format

```
{device_name}_{YYYYMMDD_HHMMSS}.cfg

Examples:
- spine1_20250203_143022.cfg
- leaf1_20250203_143045.cfg
```

## Command-Line Usage

### Run Example Script

```bash
# Make executable
chmod +x examples/backup_example.py

# Run examples
python3 examples/backup_example.py
```

### Run Module Directly

```bash
cd src
python3 backup.py
```

## Scheduled Backups (Cron)

```bash
# Add to crontab: Daily backup at 2 AM
0 2 * * * cd /path/to/project && python3 -c "from src.backup import ConfigBackup; ConfigBackup().backup_all_devices()"

# Or use a script
0 2 * * * /path/to/project/scripts/daily_backup.sh
```

## Logging

```python
from src.utils import setup_logging

# Enable logging
logger = setup_logging(
    log_level="DEBUG",              # DEBUG, INFO, WARNING, ERROR
    log_file="logs/backup.log"
)

# Then use ConfigBackup normally
backup_mgr = ConfigBackup()
```

## Error Handling

```python
result = backup_mgr.backup_device(device)

if not result['success']:
    error = result['error']

    if 'Authentication' in error:
        print("Check credentials")
    elif 'not reachable' in error:
        print("Check network connectivity")
    else:
        print(f"Error: {error}")
```

## Integration Example

### Daily Backup Script

```python
#!/usr/bin/env python3
from src.backup import ConfigBackup
from src.utils import setup_logging

# Setup
logger = setup_logging(log_level="INFO", log_file="logs/daily.log")
backup_mgr = ConfigBackup(retention_days=30)

# Backup all devices
results = backup_mgr.backup_all_devices(parallel=True)

# Report
print(backup_mgr.generate_backup_report(results))

# Cleanup
cleanup = backup_mgr.cleanup_old_backups()
logger.info(f"Cleaned up {cleanup['deleted_count']} old backups")
```

## File Locations

```
project/
├── src/backup.py                    # Core module
├── configs/backups/                 # Backup storage
│   ├── spine1_20250203_143022.cfg
│   ├── spine2_20250203_143025.cfg
│   └── ...
├── docs/BACKUP_USAGE.md            # Full documentation
├── examples/backup_example.py       # Usage examples
└── logs/                           # Log files
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: netmiko` | Run `pip install -r requirements.txt` |
| Connection timeout | Check device IP, network connectivity |
| Authentication failed | Verify credentials in inventory |
| Backup file empty | Check device type, command compatibility |
| Permission denied | Check file system permissions for backup_dir |

## Additional Resources

- **Full Documentation:** [docs/BACKUP_USAGE.md](docs/BACKUP_USAGE.md)
- **Implementation Details:** [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Examples:** [examples/backup_example.py](examples/backup_example.py)
- **Module Source:** [src/backup.py](src/backup.py)

## Quick Test

```bash
# Test structure (no devices needed)
cd tests
python3 test_backup_structure.py

# Test with real devices
cd examples
python3 backup_example.py
```
