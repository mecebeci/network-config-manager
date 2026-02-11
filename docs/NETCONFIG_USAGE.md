# NetConfig - Unified CLI Usage Guide

NetConfig is a unified command-line interface for network device configuration management. It combines backup, deployment, rollback, and administrative operations into a single professional tool.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Make the script executable (optional)
chmod +x netconfig.py

# Get help
python3 netconfig.py --help

# Or if executable
./netconfig.py --help
```

## Global Options

These options can be used with any subcommand:

```bash
--verbose, -v         Enable verbose output (debug info)
--quiet, -q           Minimal output (errors only)
--config PATH         Path to inventory file (default: inventory/devices.yaml)
--version             Show version and exit
```

## Commands

### 1. backup - Backup Device Configurations

Backup network device configurations to local files.

**Usage:**
```bash
netconfig backup [options]
```

**Device Selection:**
- `--device, -d NAME`     Backup specific device(s) (can be repeated)
- `--role, -r ROLE`       Backup all devices with role (e.g., spine, leaf)
- `--all, -a`             Backup all devices in inventory

**Backup Options:**
- `--backup-dir PATH`     Custom backup directory (default: configs/backups)
- `--parallel`            Enable parallel execution (default)
- `--no-parallel`         Disable parallel execution (sequential)
- `--yes, -y`             Skip confirmation prompt

**Examples:**
```bash
# Backup all devices in parallel
netconfig backup --all

# Backup specific devices
netconfig backup --device spine1 --device leaf1

# Backup all spine devices sequentially
netconfig backup --role spine --no-parallel

# Backup with custom directory
netconfig backup --all --backup-dir /tmp/backups

# Backup quietly (no output except errors)
netconfig backup --all --quiet

# Backup with verbose output
netconfig backup --all --verbose
```

### 2. deploy - Deploy Configurations from Templates

Deploy network configurations using Jinja2 templates.

**Usage:**
```bash
netconfig deploy --template TEMPLATE [options]
```

**Required:**
- `--template, -t NAME`   Template file name (e.g., ntp_config.j2)

**Device Selection:**
- `--device, -d NAME`     Deploy to specific device(s) (can be repeated)
- `--role, -r ROLE`       Deploy to all devices with role
- `--all, -a`             Deploy to all devices

**Deployment Options:**
- `--variables, --vars`   JSON string or file path (prefix with @)
- `--dry-run`             Preview without applying (safe testing)
- `--no-backup`           Skip automatic pre-deployment backup (caution!)
- `--parallel`            Enable parallel deployment
- `--yes, -y`             Skip confirmation prompt

**Examples:**
```bash
# Deploy to all devices with inline variables
netconfig deploy -t ntp_config.j2 --all --vars '{"ntp_server": "10.0.0.1"}'

# Deploy with variables from file
netconfig deploy -t ntp_config.j2 --device spine1 --vars @vars.json

# Preview deployment (dry-run)
netconfig deploy -t ntp_config.j2 --device spine1 --vars '{"server": "10.0.0.1"}' --dry-run

# Deploy to spine devices without confirmation
netconfig deploy -t snmp_config.j2 --role spine --vars '{"community": "public"}' --yes

# Deploy without pre-deployment backup (not recommended)
netconfig deploy -t config.j2 --device leaf1 --vars @vars.json --no-backup

# Parallel deployment to all devices
netconfig deploy -t ntp.j2 --all --vars '{"server": "10.0.0.1"}' --parallel
```

**Variables File Format (JSON):**
```json
{
  "ntp_server": "10.0.0.1",
  "timezone": "UTC",
  "snmp_community": "public"
}
```

### 3. rollback - Rollback to Previous Configurations

Restore network devices to previous configuration backups.

**Usage:**
```bash
netconfig rollback [options]
```

**Device Selection:**
- `--device, -d NAME`     Rollback specific device(s)
- `--role, -r ROLE`       Rollback all devices with role
- `--all, -a`             Rollback all devices

**Backup Selection (choose one):**
- `--latest`              Use latest backup for each device
- `--backup, -b FILE`     Rollback to specific backup file (single device only)
- `--timestamp, -t TIME`  Rollback to backup closest to timestamp

**Execution Options:**
- `--parallel`            Enable parallel execution
- `--no-safety-backup`    Skip safety backup before rollback (caution!)
- `--dry-run`             Preview without applying
- `--yes, -y`             Skip confirmation prompt

**Examples:**
```bash
# Rollback device to latest backup
netconfig rollback --device spine1 --latest

# Rollback to specific backup file
netconfig rollback --device spine1 --backup configs/backups/spine1_20250203_143022.cfg

# Rollback multiple devices to latest
netconfig rollback --device spine1 --device leaf1 --latest

# Rollback all spine devices
netconfig rollback --role spine --latest

# Preview rollback (dry-run)
netconfig rollback --device leaf1 --latest --dry-run

# Rollback to timestamp (YYYY-MM-DD HH:MM:SS)
netconfig rollback --device spine1 --timestamp "2025-02-03 14:30:00"

# Rollback without safety backup (not recommended)
netconfig rollback --device spine1 --latest --no-safety-backup

# Parallel rollback
netconfig rollback --role leaf --latest --parallel --yes
```

### 4. list - List Resources

List and display information about devices, backups, and templates.

**Usage:**
```bash
netconfig list [--devices | --backups DEVICE | --templates] [options]
```

**List Options (choose one):**
- `--devices`             List all devices in inventory
- `--backups DEVICE`      List backups for specific device
- `--templates`           List available templates

**Output Format:**
- `--format FORMAT`       Output format: table (default), json, simple

**Examples:**
```bash
# List all devices (table format)
netconfig list --devices

# List devices in JSON format
netconfig list --devices --format json

# List devices (simple, names only)
netconfig list --devices --format simple

# List backups for device
netconfig list --backups spine1

# List backups in JSON format
netconfig list --backups spine1 --format json

# List all available templates
netconfig list --templates

# List templates (simple format)
netconfig list --templates --format simple
```

### 5. validate - Validate Resources

Validate configuration files, templates, and backups.

**Usage:**
```bash
netconfig validate [--inventory | --template NAME | --templates | --backup FILE]
```

**Validation Options (choose one):**
- `--inventory`           Validate inventory file structure
- `--template NAME`       Validate specific template syntax
- `--templates`           Validate all templates
- `--backup FILE`         Validate backup file

**Examples:**
```bash
# Validate inventory file
netconfig validate --inventory

# Validate specific template
netconfig validate --template ntp_config.j2

# Validate all templates
netconfig validate --templates

# Validate backup file
netconfig validate --backup configs/backups/spine1_20250203_143022.cfg
```

## Common Workflows

### Initial Setup and Validation
```bash
# 1. Validate inventory file
netconfig validate --inventory

# 2. List all devices
netconfig list --devices

# 3. Validate all templates
netconfig validate --templates

# 4. List available templates
netconfig list --templates
```

### Safe Deployment Workflow
```bash
# 1. Create backup before deployment
netconfig backup --all

# 2. Preview deployment (dry-run)
netconfig deploy -t ntp.j2 --all --vars '{"server": "10.0.0.1"}' --dry-run

# 3. Deploy with automatic backup
netconfig deploy -t ntp.j2 --all --vars '{"server": "10.0.0.1"}'

# 4. Verify deployment success
# (check output and logs)

# 5. If needed, rollback to previous state
netconfig rollback --all --latest
```

### Testing Templates
```bash
# 1. Validate template syntax
netconfig validate --template new_config.j2

# 2. Test on single device (dry-run)
netconfig deploy -t new_config.j2 --device spine1 --vars @test_vars.json --dry-run

# 3. Deploy to single device
netconfig deploy -t new_config.j2 --device spine1 --vars @test_vars.json

# 4. If successful, deploy to all
netconfig deploy -t new_config.j2 --all --vars @test_vars.json
```

### Rollback Workflow
```bash
# 1. List available backups
netconfig list --backups spine1

# 2. Preview rollback (dry-run)
netconfig rollback --device spine1 --latest --dry-run

# 3. Execute rollback with safety backup
netconfig rollback --device spine1 --latest

# 4. Verify rollback success
# (check device configuration)
```

### Bulk Operations
```bash
# Backup all devices
netconfig backup --all --parallel

# Deploy configuration to all spine switches
netconfig deploy -t spine_config.j2 --role spine --vars @spine_vars.json --parallel

# Rollback all leaf switches to latest backup
netconfig rollback --role leaf --latest --parallel
```

## Exit Codes

- `0` - Success
- `1` - Failure (some operations failed)
- `2` - Error (invalid arguments, file not found, etc.)
- `130` - Cancelled by user (Ctrl+C)

## Tips and Best Practices

1. **Always use dry-run first**: Test deployments with `--dry-run` before applying
2. **Enable verbose output for debugging**: Use `-v` to see detailed information
3. **Automatic backups are recommended**: Don't use `--no-backup` unless necessary
4. **Safety backups before rollback**: Don't use `--no-safety-backup` unless necessary
5. **Use parallel execution for speed**: Add `--parallel` for bulk operations
6. **Validate before deployment**: Always validate templates and inventory first
7. **Keep backups organized**: Use default backup directory structure
8. **Use variables files for complex deployments**: Store variables in JSON files with `@file.json`

## Troubleshooting

### Import Errors
```bash
# Install dependencies
pip install -r requirements.txt

# Or install individually
pip install netmiko pyyaml jinja2 python-dotenv tabulate
```

### Connection Issues
```bash
# Use verbose mode to see connection details
netconfig backup --device spine1 --verbose

# Check inventory file
netconfig validate --inventory

# Verify device is reachable
ping <device_ip>
```

### Template Errors
```bash
# Validate template syntax
netconfig validate --template mytemplate.j2

# List available templates
netconfig list --templates

# Use dry-run to test
netconfig deploy -t mytemplate.j2 --device test --vars '{}' --dry-run
```

### Backup/Rollback Issues
```bash
# List available backups
netconfig list --backups <device_name>

# Validate backup file
netconfig validate --backup <backup_file>

# Check backup directory permissions
ls -la configs/backups/
```

## Shell Completion (Optional)

For bash command completion:

```bash
# Install argcomplete
pip install argcomplete

# Add to ~/.bashrc
eval "$(register-python-argcomplete netconfig)"

# Reload shell
source ~/.bashrc
```

## Version

NetConfig version 1.0.0

## Related Files

- `netconfig.py` - Main unified CLI entry point
- `backup_devices.py` - Original backup CLI (still works)
- `deploy_config.py` - Original deploy CLI (still works)
- `rollback_config.py` - Original rollback CLI (still works)
- `inventory/devices.yaml` - Device inventory file
- `configs/templates/` - Jinja2 template directory
- `configs/backups/` - Backup storage directory

---
