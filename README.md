# Network Configuration Management System

A comprehensive Python-based solution for automating multi-device network configuration management for SR Linux devices. This system eliminates repetitive manual tasks by providing automated backup, template-based deployment, and rollback capabilities through Containerlab virtualization.

## Project Overview

**Project Name:** Network Configuration Management System

**Purpose:** This project automates repetitive network configuration tasks, enabling network engineers to manage multiple devices simultaneously instead of manually logging into each device individually. It provides centralized configuration management with automated backups, template-based deployment, and safe rollback capabilities for SR Linux network infrastructure.

**Real-World Problem It Solves:**

Imagine managing 50 network devices where you need to change the NTP server configuration across all of them. Traditionally, this would require SSH access to each device individually, executing commands 50 times, and manually tracking changes. This project allows you to define the configuration once and deploy it automatically to all devices, with built-in safety mechanisms including automated backups and dry-run validation.

## Core Features

### 1. Configuration Backup
- **Automated backup with timestamps** - Schedule and execute automatic configuration backups with timestamp-based version control
- **Single and multi-device backup** - Backup individual devices or entire network segments
- **Parallel execution support** - Run backups concurrently for faster operations
- **Backup retention and rotation** - Maintain historical configurations for audit and recovery

### 2. Configuration Deployment
- **Jinja2 template-based deployment** - Deploy standardized configurations using templates with device-specific variables
- **Dry-run mode for testing** - Preview configuration changes before applying them to production
- **Automatic pre-deployment backup** - Safety backup created before every deployment
- **Rollback on failure** - Automatic restoration if deployment fails
- **Variable substitution** - Dynamic configuration generation based on device attributes

### 3. Configuration Rollback
- **Restore from any previous backup** - Access complete configuration history
- **Interactive backup selection** - Choose from chronologically sorted backup list
- **Safety backup before rollback** - Current configuration saved before restoration
- **Timestamp-based rollback** - Easy identification of restore points

### 4. Multi-Device Operations
- **Parallel execution for speed** - Concurrent operations across multiple devices
- **Device filtering by name or role** - Target specific devices or groups (spine/leaf)
- **Comprehensive error handling** - Graceful handling of failures with detailed reporting

## Technology Stack

- **Python 3.x** - Core programming language
- **Netmiko** - SSH automation for network devices
- **Jinja2** - Configuration template engine
- **PyYAML** - Inventory management
- **Containerlab** - Lab environment virtualization
- **Nokia SR Linux** - Network operating system

## Project Architecture

### Layer 1 - User Interface
Command-line interface for executing operations with support for various options including device targeting, template selection, and dry-run validation.

### Layer 2 - Application Logic
Python modules handling business logic including inventory management, connection handling, command execution, error management, and configuration operations.

### Layer 3 - Network Communication
**Netmiko** provides SSH connection management and command execution, abstracting low-level protocol details.

### Layer 4 - Network Devices
SR Linux containers running in Containerlab, receiving SSH connections, executing commands, and returning results.

## Project Structure

```
network-automation-snmp/
├── README.md                 # Project documentation
├── requirements.txt         # Python dependencies
├── .gitignore               # Git ignore rules
├── .env.example            # Environment variables template
├── backup_devices.py        # Backup CLI
├── deploy_config.py         # Deployment CLI
├── rollback_config.py       # Rollback CLI
├── inventory/              # Device inventory
│   ├── devices.yaml        # Device definitions
│   └── README.md           # Inventory documentation
├── configs/                # Configuration management
│   ├── backups/           # Stored backups
│   └── templates/         # Jinja2 templates
├── src/                    # Source code modules
│   ├── backup.py          # Backup module
│   ├── deployment.py      # Deployment module
│   ├── rollback.py        # Rollback module
│   ├── connection_manager.py  # SSH connections
│   ├── inventory_loader.py    # Inventory management
│   ├── template_engine.py     # Template rendering
│   ├── utils.py           # Utilities
│   └── exceptions.py      # Custom exceptions
├── lab/                    # Containerlab topology
│   ├── topology.yaml      # Lab topology definition
│   └── README.md          # Lab documentation
└── logs/                   # Application logs
```

## Workflow Examples

### Workflow 1 - Daily Backup
Schedule the backup script to run nightly at midnight. The script loads the inventory, connects to each device, retrieves running configurations, saves them with timestamps, and generates a summary report. Morning verification ensures fresh backups exist for all devices.

### Workflow 2 - Configuration Change
To add a new NTP server across all devices:
1. Create a Jinja2 template file with NTP configuration commands
2. Run deployment script in dry-run mode to preview changes
3. Review the dry-run output for accuracy
4. Execute deployment for real (automatic pre-deployment backup occurs)
5. Script applies template commands and commits changes
6. Review success/failure summary

### Workflow 3 - Emergency Rollback
When a configuration change causes issues:
1. Run rollback script and select the affected device
2. View chronologically sorted list of available backups
3. Select backup from before the problematic change
4. Confirm restoration choice
5. Script restores the selected configuration
6. Verify device functionality

## Lab Topology

The project includes a six-device SR Linux spine-leaf topology with 2 spine switches and 4 leaf switches:

```
        [Spine1]         [Spine2]
        /  |  \  \       /  /  |  \
       /   |   \  \     /  /   |   \
   [Leaf1] [Leaf2] [Leaf3] [Leaf4]
```

### Device Details
- **Spine1**: Core spine switch connecting all leaf switches (172.20.20.11)
- **Spine2**: Core spine switch connecting all leaf switches (172.20.20.12)
- **Leaf1**: Top-of-Rack switch with dual uplinks to both spines (172.20.20.13)
- **Leaf2**: Top-of-Rack switch with dual uplinks to both spines (172.20.20.14)
- **Leaf3**: Top-of-Rack switch with dual uplinks to both spines (172.20.20.15)
- **Leaf4**: Top-of-Rack switch with dual uplinks to both spines (172.20.20.16)

### Connections
Each leaf switch is dual-homed to both spine switches for redundancy:
- Spine1 e1-1 ↔ Leaf1 e1-1, Spine2 e1-1 ↔ Leaf1 e1-2
- Spine1 e1-2 ↔ Leaf2 e1-1, Spine2 e1-2 ↔ Leaf2 e1-2
- Spine1 e1-3 ↔ Leaf3 e1-1, Spine2 e1-3 ↔ Leaf3 e1-2
- Spine1 e1-4 ↔ Leaf4 e1-1, Spine2 e1-4 ↔ Leaf4 e1-2

### IP Addressing
Containerlab automatically assigns management IPs from the 172.20.20.0/24 subnet, used for SSH access.

## Module Descriptions

### Backup Module
Connects to devices via SSH, executes show commands to retrieve current configurations, and saves output to timestamped files (e.g., `spine1_2025-01-15_14-30-00.txt`). Provides configuration history for audit and recovery purposes.

### Deployment Module
Reads Jinja2 templates containing configuration commands, performs variable substitution for device-specific values (hostname, IP addresses), connects to target devices, and applies configurations. Automatically creates pre-deployment backups for safety.

### Rollback Module
Lists all available backups for selected devices sorted by date (newest first), allows interactive selection of restore point, and applies the historical configuration to recover from problematic changes.

### Connection Manager
Manages SSH connections to network devices using Netmiko, handles authentication, connection pooling, and error recovery for robust network communication.

### Template Engine
Processes Jinja2 templates with device-specific variables to generate dynamic configurations, supporting conditional logic and loops for complex configuration scenarios.

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Containerlab installed and configured
- SR Linux container images
- Git for version control

### Setup Steps

1. Clone the repository:
```bash
git clone <repository-url>
cd network-automation-snmp
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

5. Create inventory file:
```bash
# Edit inventory/devices.yaml with your device details
```

6. Deploy lab topology (optional):
```bash
cd lab
sudo containerlab deploy -t topology.yaml
```

## Usage Examples

### Backup Operations

```bash
# Backup all devices
python backup_devices.py --all

# Backup specific devices
python backup_devices.py --device spine1 --device leaf1

# Backup by role
python backup_devices.py --role spine

# Backup with parallel execution
python backup_devices.py --all --parallel
```

### Deployment Operations

```bash
# Preview deployment (dry-run)
python deploy_config.py --device spine1 --template ntp_config.j2 \
  --vars '{"ntp_server": "10.0.0.1"}' --dry-run

# Deploy to all devices
python deploy_config.py --all --template ntp_config.j2 \
  --vars '{"ntp_server": "10.0.0.1"}'

# Deploy to specific role
python deploy_config.py --role spine --template snmp_config.j2 \
  --vars @variables.json

# Deploy without backup (not recommended)
python deploy_config.py --device leaf1 --template base_config.j2 \
  --no-backup
```

### Rollback Operations

```bash
# List available backups for a device
python rollback_config.py --list spine1

# Rollback to latest backup
python rollback_config.py --device spine1 --latest

# Interactive rollback (choose from list)
python rollback_config.py --device spine1

# Rollback with dry-run
python rollback_config.py --device spine1 --latest --dry-run
```

## Command Line Interface

### Common Arguments
- `--inventory, -i`: Path to inventory file (default: `inventory/devices.yaml`)
- `--device, -d`: Target specific device by name (can be used multiple times)
- `--role, -r`: Filter devices by role (spine or leaf)
- `--all, -a`: Target all devices in inventory
- `--parallel, -p`: Execute operations in parallel

### Backup-Specific Arguments
- `--backup-dir, -b`: Directory for storing backup files (default: `configs/backups`)

### Deployment-Specific Arguments
- `--template, -t`: Configuration template to deploy (required)
- `--vars, -v`: Template variables as JSON string or @file.json
- `--dry-run`: Preview changes without applying them
- `--no-backup`: Skip automatic pre-deployment backup

### Rollback-Specific Arguments
- `--list, -l`: List available backups for specified device
- `--latest`: Rollback to the most recent backup
- `--backup-file, -f`: Specify exact backup file to restore
- `--dry-run`: Preview rollback without applying changes

## Error Handling

The system implements comprehensive error handling:

- **Connection Failures**: Logs errors, marks devices as failed, continues with remaining devices
- **Authentication Failures**: Catches authentication exceptions, logs issues, proceeds to next device
- **Timeout Handling**: Gracefully handles device response timeouts without crashing
- **Template Errors**: Validates templates and variables before deployment
- **Results Tracking**: Maintains separate lists of successful and failed operations with detailed error messages

All operations provide final summaries showing both successful completions and failures with specific error details.

## Safety Features

### Pre-Deployment Backups
Every deployment automatically creates a backup of the current configuration before applying changes, ensuring you can always revert if needed.

### Dry-Run Mode
Test configuration changes without actually applying them to devices. Review the exact commands that would be executed.

### Rollback Safety Backup
Before performing a rollback, the system creates a safety backup of the current configuration, preventing data loss.

### Parallel Execution Safety
Even with parallel execution, the system maintains proper error isolation and ensures failures on one device don't affect operations on others.

## Quick Start Guide

1. **Setup your lab environment**:
```bash
cd lab
sudo containerlab deploy -t topology.yaml
```

2. **Configure your inventory**:
Edit `inventory/devices.yaml` with your device details.

3. **Take an initial backup**:
```bash
python backup_devices.py --all
```

4. **Create a configuration template**:
Create a Jinja2 template in `configs/templates/`.

5. **Test your deployment**:
```bash
python deploy_config.py --device spine1 --template your_template.j2 --dry-run
```

6. **Deploy the configuration**:
```bash
python deploy_config.py --all --template your_template.j2
```

7. **Rollback if needed**:
```bash
python rollback_config.py --device spine1 --latest
```

## Why This Project Matters

This project demonstrates practical skills directly applicable to network engineering and automation roles:

- **Network Automation Skills**: Python-based automation, Netmiko usage, configuration management
- **Infrastructure as Code**: Template-based configuration management with version control
- **Practical Experience**: Working code demonstrating real-world problem-solving
- **Documentation Skills**: Professional documentation and code organization
- **Lab Environment**: Containerlab proficiency for safe pre-production testing
- **Design Decisions**: Thoughtful architecture with separation of concerns and maintainability
- **Safety-First Approach**: Built-in safeguards for production environment operations

## Future Enhancements

- Support for additional network device vendors and platforms (Cisco, Arista, Juniper)
- Web-based dashboard for configuration management
- Scheduled backup automation with retention policies
- Configuration compliance checking and drift detection
- Configuration versioning with Git integration
- REST API for programmatic access
- Ansible playbook integration
- Advanced template library with common configurations
- Multi-site configuration synchronization
- Configuration change approval workflows

---
