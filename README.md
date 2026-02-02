# Network Automation and SNMP Monitoring System

A comprehensive Python-based solution for automating multi-device network configuration management and monitoring SR Linux devices. This system eliminates repetitive manual tasks by providing automated backup, deployment, rollback capabilities, and real-time SNMP monitoring through Containerlab virtualization.

## Project Overview

**Project Name:** Multi-Device Network Automation and SNMP Monitoring System

**Purpose:** This project automates repetitive network management tasks, enabling network engineers to manage multiple devices simultaneously instead of manually logging into each device individually. It provides centralized configuration management, automated backups, and comprehensive health monitoring for SR Linux network infrastructure.

**Real-World Problem It Solves:**

Imagine managing 50 network devices where you need to change the NTP server configuration across all of them. Traditionally, this would require SSH access to each device individually, executing commands 50 times, and manually tracking changes. This project allows you to define the configuration once and deploy it automatically to all devices, with built-in safety mechanisms including automated backups and dry-run validation.

## Key Features

### Configuration Management
- **Automated Backup**: Schedule and execute automatic configuration backups with timestamp-based version control
- **Template-Based Deployment**: Deploy standardized configurations using Jinja2 templates with device-specific variable substitution
- **Configuration Rollback**: Quick restoration to previous working configurations with interactive backup selection
- **Dry-Run Mode**: Preview configuration changes before applying them to production devices

### Network Monitoring
- **SNMP Monitoring**: Real-time collection of device metrics including uptime, interface traffic, and operational status
- **Visual Reporting**: Automated generation of traffic charts, uptime visualizations, and interface status reports
- **JSON Export**: Export collected metrics for integration with external monitoring systems
- **Multi-Device Health Checks**: Simultaneous monitoring across entire network infrastructure

### Safety and Reliability
- **Pre-Deployment Backups**: Automatic backup creation before any configuration changes
- **Error Handling**: Graceful handling of connection failures, authentication errors, and timeouts
- **Results Tracking**: Comprehensive success/failure reporting for all operations
- **Device Filtering**: Target specific devices or roles (spine/leaf) for selective operations

## Technology Stack

- **Python 3.8+**: Core programming language
- **Netmiko 4.3.0+**: Multi-vendor SSH library for network device automation
- **PySNMP 4.4.12+**: SNMP protocol implementation for network monitoring
- **Matplotlib 3.8.0+**: Data visualization and chart generation
- **Containerlab**: Network topology virtualization platform
- **SR Linux**: Nokia's network operating system for data center networking
- **Jinja2 3.1.2+**: Configuration template engine
- **PyYAML 6.0.1+**: YAML parser for inventory and configuration files
- **python-dotenv 1.0.0+**: Environment variable management
- **Tabulate 0.9.0+**: Formatted console output tables

## Project Architecture

### Layer 1 - User Interface
Command-line interface for executing operations with support for various options including device targeting, template selection, and dry-run validation.

### Layer 2 - Application Logic
Python modules handling business logic including inventory management, connection handling, command execution, error management, and report generation.

### Layer 3 - Network Communication
- **Netmiko**: SSH connection management and command execution
- **PySNMP**: SNMP queries and metric collection
- Abstraction of low-level protocol details

### Layer 4 - Network Devices
SR Linux containers running in Containerlab, receiving SSH connections and SNMP queries, executing commands, and returning results.

## Project Structure

```
network-automation-snmp/
├── README.md                 # Project documentation
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── inventory/              # Device inventory files (YAML)
│   └── devices.yaml        # Device definitions with credentials and SNMP settings
├── configs/                # Configuration management
│   ├── backups/           # Timestamped device configuration backups
│   └── templates/         # Jinja2 configuration templates
├── src/                    # Source code modules
│   ├── backup.py          # Configuration backup module
│   ├── deploy.py          # Configuration deployment module
│   ├── rollback.py        # Configuration rollback module
│   ├── monitor.py         # SNMP monitoring module
│   └── utils.py           # Shared utility functions
├── reports/                # Generated monitoring reports and charts
│   ├── traffic_*.png      # Traffic comparison charts
│   ├── uptime_*.png       # Device uptime visualizations
│   └── metrics_*.json     # Exported metric data
├── lab/                    # Containerlab topology definitions
│   └── topology.yml       # SR Linux spine-leaf topology
└── logs/                   # Application logs and operation history
```

## Workflow Examples

### Workflow 1 - Daily Backup
Schedule the backup script to run nightly at midnight. The script loads the inventory, connects to each device sequentially, retrieves running configurations, saves them with timestamps, and generates a summary report. Morning verification ensures fresh backups exist for all devices.

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

### Workflow 4 - Health Check
To assess network health:
1. Run SNMP monitoring script
2. Script queries each device for uptime, traffic counters, and interface states
3. Console displays summary table with device uptimes and traffic totals
4. PNG charts generated showing:
   - Traffic comparison across devices (inbound/outbound)
   - Uptime visualization with health color coding
   - Interface status distribution (up/down)
5. Optional JSON export for external processing

## Lab Topology

The project includes a six-device SR Linux spine-leaf topology with 2 spine switches and 4 leaf switches:

```
        [Spine1]         [Spine2]
        /  |  \  \       /  /  |  \
       /   |   \  \     /  /   |   \
   [Leaf1] [Leaf2] [Leaf3] [Leaf4]
```

### Device Details
- **Spine1**: Core spine switch connecting all leaf switches (172.21.20.11)
- **Spine2**: Core spine switch connecting all leaf switches (172.21.20.12)
- **Leaf1**: Top-of-Rack switch with dual uplinks to both spines (172.21.20.13)
- **Leaf2**: Top-of-Rack switch with dual uplinks to both spines (172.21.20.14)
- **Leaf3**: Top-of-Rack switch with dual uplinks to both spines (172.21.20.15)
- **Leaf4**: Top-of-Rack switch with dual uplinks to both spines (172.21.20.16)

### Connections
Each leaf switch is dual-homed to both spine switches for redundancy:
- Spine1 e1-1 ↔ Leaf1 e1-1, Spine2 e1-1 ↔ Leaf1 e1-2
- Spine1 e1-2 ↔ Leaf2 e1-1, Spine2 e1-2 ↔ Leaf2 e1-2
- Spine1 e1-3 ↔ Leaf3 e1-1, Spine2 e1-3 ↔ Leaf3 e1-2
- Spine1 e1-4 ↔ Leaf4 e1-1, Spine2 e1-4 ↔ Leaf4 e1-2

### IP Addressing
Containerlab automatically assigns management IPs from the 172.21.20.0/24 subnet, used for SSH and SNMP access.

## Module Descriptions

### Backup Module
Connects to devices via SSH, executes show commands to retrieve current configurations, and saves output to timestamped files (e.g., `spine1_2025-01-15_14-30-00.txt`). Provides configuration history for audit and recovery purposes.

### Deployment Module
Reads Jinja2 templates containing configuration commands, performs variable substitution for device-specific values (hostname, IP addresses), connects to target devices, and applies configurations. Automatically creates pre-deployment backups for safety.

### Rollback Module
Lists all available backups for selected devices sorted by date (newest first), allows interactive selection of restore point, and applies the historical configuration to recover from problematic changes.

### SNMP Monitoring Module
Queries devices using SNMP protocol to collect:
- System uptime (time since last reboot)
- Interface traffic counters (inbound/outbound octets)
- Interface operational status (up/down states)

Generates visual charts with Matplotlib:
- **Traffic Chart**: Bar chart comparing traffic across devices
- **Uptime Chart**: Horizontal bar chart with color-coded health indicators
- **Interface Status Chart**: Pie chart showing interface state distribution

## Command Line Interface

### Common Arguments
- `--inventory, -i`: Path to inventory file (default: `inventory/devices.yaml`)
- `--device, -d`: Target specific device by name
- `--role, -r`: Filter devices by role (spine or leaf)

### Backup-Specific Arguments
- `--backup-dir, -b`: Directory for storing backup files

### Deployment-Specific Arguments
- `--template, -t`: Configuration template to deploy (required)
- `--dry-run`: Preview changes without applying them
- `--no-backup`: Skip automatic pre-deployment backup

### Monitoring-Specific Arguments
- `--output-dir, -o`: Directory for saving charts
- `--no-charts`: Skip chart generation
- `--export-json`: Save metrics to JSON file

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
sudo containerlab deploy -t topology.yml
```

## Usage

### Backup All Devices
```bash
python src/backup.py
```

### Backup Specific Device
```bash
python src/backup.py --device spine1
```

### Deploy Configuration Template
```bash
python src/deploy.py --template configs/templates/ntp.j2
```

### Deploy with Dry-Run
```bash
python src/deploy.py --template configs/templates/ntp.j2 --dry-run
```

### Rollback Configuration
```bash
python src/rollback.py --device leaf1
```

### Monitor Network Health
```bash
python src/monitor.py
```

### Monitor Specific Role
```bash
python src/monitor.py --role spine
```

## Error Handling

The system implements comprehensive error handling:

- **Connection Failures**: Logs errors, marks devices as failed, continues with remaining devices
- **Authentication Failures**: Catches authentication exceptions, logs issues, proceeds to next device
- **Timeout Handling**: Gracefully handles device response timeouts without crashing
- **Results Tracking**: Maintains separate lists of successful and failed operations with detailed error messages

All operations provide final summaries showing both successful completions and failures with specific error details.

## Why This Project Matters

This project demonstrates practical skills directly applicable to network engineering and automation roles:

- **Network Automation Skills**: Python-based automation, Netmiko usage, configuration management
- **SNMP Knowledge**: Understanding of SNMP protocol, OIDs, and metric collection
- **Practical Experience**: Working code demonstrating real-world problem-solving
- **Documentation Skills**: Professional documentation and code organization
- **Lab Environment**: Containerlab proficiency for safe pre-production testing
- **Design Decisions**: Thoughtful architecture with separation of concerns and maintainability

## Future Enhancements

- Support for additional network device vendors and platforms
- Web-based dashboard for monitoring and configuration management
- Scheduled backup automation with retention policies
- Configuration compliance checking and drift detection
- Integration with external monitoring systems (Grafana, Prometheus)
- REST API for programmatic access
- Ansible playbook integration
- Multi-threading for improved performance with large device inventories

---
