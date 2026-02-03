# Network Device Backup CLI

Command-line interface for backing up network device configurations.

## Installation

The CLI script is located at the project root: `backup_devices.py`

Make sure you have activated the virtual environment before running:

```bash
source .venv/bin/activate
```

## Quick Start

```bash
# Backup all devices
python3 backup_devices.py --all

# Backup specific devices
python3 backup_devices.py --device spine1 --device leaf1

# Backup by role
python3 backup_devices.py --role spine

# Backup with verbose output
python3 backup_devices.py --all --verbose
```

## Usage

```
python3 backup_devices.py [OPTIONS]
```

### Device Selection Options

| Option | Short | Description |
|--------|-------|-------------|
| `--device NAME` | `-d` | Backup specific device(s) by name (can be repeated) |
| `--role ROLE` | `-r` | Backup all devices with specific role (e.g., spine, leaf) |
| `--all` | `-a` | Backup all devices in inventory (default if no filters) |

### Execution Options

| Option | Description |
|--------|-------------|
| `--parallel` | Enable parallel execution (default) |
| `--no-parallel` | Disable parallel execution (sequential mode) |
| `--backup-dir PATH` | Custom backup directory (default: configs/backups) |
| `--yes` or `-y` | Skip confirmation prompt |

### Output Options

| Option | Short | Description |
|--------|-------|-------------|
| `--verbose` | `-v` | Enable verbose output (DEBUG level logging) |
| `--quiet` | `-q` | Minimal output (only show errors) |

## Examples

### Backup All Devices

```bash
python3 backup_devices.py --all
```

This will:
- Load all devices from inventory
- Display backup plan with device list
- Ask for confirmation
- Execute backup in parallel
- Show detailed results

### Backup Specific Devices

```bash
# Single device
python3 backup_devices.py --device spine1

# Multiple devices
python3 backup_devices.py --device spine1 --device leaf1 --device leaf2
```

### Backup by Role

```bash
# Backup all spine switches
python3 backup_devices.py --role spine

# Backup all leaf switches
python3 backup_devices.py --role leaf
```

### Sequential Backup (No Parallel)

```bash
python3 backup_devices.py --all --no-parallel
```

This is useful for:
- Debugging connection issues
- Reducing network load
- Systems with limited resources

### Verbose Output

```bash
python3 backup_devices.py --all --verbose
```

Shows:
- DEBUG level logs
- Connection details
- Command execution details
- File operations

### Quiet Mode

```bash
python3 backup_devices.py --all --quiet
```

Only displays:
- Errors (if any occur)
- No progress information
- No success messages

Useful for:
- Cron jobs
- Automated scripts
- Log file reduction

### Custom Backup Directory

```bash
python3 backup_devices.py --all --backup-dir /tmp/backups
```

### Skip Confirmation

```bash
python3 backup_devices.py --all --yes
```

Useful for:
- Automated scripts
- Cron jobs
- CI/CD pipelines

### Combined Options

```bash
# Backup spine switches, sequentially, with verbose output, skip confirmation
python3 backup_devices.py --role spine --no-parallel --verbose --yes

# Backup specific devices to custom directory, quiet mode
python3 backup_devices.py --device spine1 --device spine2 --backup-dir /custom/path --quiet --yes
```

## Output Format

### Normal Mode

```
================================================================================
BACKUP PLAN
================================================================================

Devices to backup: 2
Execution mode: Parallel
Backup directory: configs/backups

Device List:
+--------+--------------+--------+---------------+
| Name   | IP Address   | Role   | Device Type   |
+========+==============+========+===============+
| spine1 | 172.21.20.11 | spine  | nokia_sros    |
+--------+--------------+--------+---------------+
| spine2 | 172.21.20.12 | spine  | nokia_sros    |
+--------+--------------+--------+---------------+

================================================================================
BACKUP RESULTS
================================================================================

Total devices: 2
Successful: 2
Failed: 0
Success rate: 100.0%
Total backup size: 0.15 MB
Execution time: 12.5 seconds

--------------------------------------------------------------------------------
SUCCESSFUL BACKUPS
--------------------------------------------------------------------------------
✓ spine1          -> spine1_20250203_143022.cfg (75.2 KB)
✓ spine2          -> spine2_20250203_143028.cfg (78.5 KB)
```

### Quiet Mode

Only errors are shown:
```
✗ spine1: Connection timeout - Device not reachable
```

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | All backups completed successfully |
| 1 | One or more backups failed |
| 2 | Error (invalid arguments, missing inventory, etc.) |

## Error Handling

### Invalid Device Name

```bash
$ python3 backup_devices.py --device nonexistent
✗ Device 'nonexistent' not found in inventory
ℹ Available devices:
  - spine1
  - spine2
  - leaf1
  - leaf2
  - leaf3
  - leaf4
```

### Invalid Role

```bash
$ python3 backup_devices.py --role invalid
✗ No devices found with role 'invalid'
ℹ Available roles:
  - spine (2 devices)
  - leaf (4 devices)
```

### Missing Inventory File

```bash
✗ Inventory file not found: FileNotFoundError(...)
ℹ Make sure you're running from the project root directory
```

## Integration with Other Tools

### Cron Job

```bash
# Add to crontab for daily backups at 2 AM
0 2 * * * cd /path/to/project && source .venv/bin/activate && python3 backup_devices.py --all --quiet --yes >> /var/log/network-backup.log 2>&1
```

### Shell Script

```bash
#!/bin/bash
cd /path/to/project
source .venv/bin/activate

python3 backup_devices.py --all --yes

if [ $? -eq 0 ]; then
    echo "Backup successful"
    # Additional actions (e.g., upload to S3, send notification)
else
    echo "Backup failed"
    # Alert/notification logic
fi
```

### Check Exit Code

```bash
python3 backup_devices.py --all --yes
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "All backups successful"
elif [ $EXIT_CODE -eq 1 ]; then
    echo "Some backups failed"
else
    echo "Error occurred"
fi
```

## Logging

All operations are logged to: `logs/network_automation.log`

The log file contains:
- Timestamps for all operations
- Connection attempts and results
- Command execution details
- Error messages with full stack traces (in verbose mode)

## Tips

1. **Test First**: Use `--device` with a single device to test before backing up all devices
2. **Use Verbose Mode**: When troubleshooting, use `--verbose` to see detailed logs
3. **Sequential for Debugging**: Use `--no-parallel` when debugging connection issues
4. **Custom Directory**: Use `--backup-dir` for one-time backups to different locations
5. **Automation**: Combine `--yes` and `--quiet` for automated/cron jobs

## Troubleshooting

### Import Errors

If you see import errors, make sure you're running from the project root:
```bash
cd /path/to/network-automation-snmp
source .venv/bin/activate
python3 backup_devices.py --help
```

### Connection Timeouts

- Verify devices are reachable: `ping <device-ip>`
- Check Containerlab is running: `sudo containerlab inspect`
- Use verbose mode to see connection details: `--verbose`

### Permission Errors

- Ensure backup directory is writable
- Check log directory permissions

---
