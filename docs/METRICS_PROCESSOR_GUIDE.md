# Metrics Processor Guide

## Overview

The **MetricsProcessor** module provides comprehensive metrics processing and analysis capabilities for SNMP data collected from network devices. It processes raw SNMP metrics, calculates statistics, aggregates data across devices, and exports results in multiple formats.

## Features

- **Process Raw Metrics** - Transform SNMP data into structured, analyzed metrics
- **Calculate Derived Metrics** - Traffic totals, utilization, error rates
- **Aggregate Across Devices** - Fleet-wide statistics and summaries
- **Multiple Export Formats** - JSON, CSV for easy integration
- **Human-Readable Reports** - Text-based summary and device reports
- **Historical Tracking** - Save metrics snapshots for trending
- **Top Performers** - Identify devices by traffic, errors
- **Traffic Formatting** - Automatic human-readable byte conversion
- **Uptime Formatting** - Convert seconds to days/hours/minutes

## Installation

The MetricsProcessor is part of the network-automation-snmp project:

```bash
# Ensure dependencies are installed
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick Start

### Basic Usage

```python
from src.metrics_processor import MetricsProcessor
from src.snmp_monitor import SNMPMonitor

# Initialize
processor = MetricsProcessor(output_dir="reports")
monitor = SNMPMonitor()

# Collect and process from a single device
device = {'name': 'spine1', 'ip': '172.20.20.11', 'snmp_enabled': True}
raw_metrics = monitor.collect_device_metrics(device)
processed = processor.process_device_metrics(raw_metrics)

# Display results
if processed['success']:
    print(f"Device: {processed['device_name']}")
    print(f"Uptime: {processor.format_uptime(processed['summary']['uptime_seconds'])}")
    print(f"Interfaces: {processed['summary']['total_interfaces']}")
    print(f"Traffic In: {processed['summary']['total_in_traffic_readable']}")
```

### Processing Multiple Devices

```python
# Collect from all SNMP-enabled devices
raw_metrics_list = monitor.collect_all_devices(parallel=True)

# Process all devices
processed_list = [processor.process_device_metrics(m) for m in raw_metrics_list]

# Aggregate metrics
aggregated = processor.aggregate_metrics(processed_list)

print(f"Total Devices: {aggregated['total_devices']}")
print(f"Total Traffic: {processor.format_traffic(aggregated['total_traffic_in'] + aggregated['total_traffic_out'])}")
print(f"Average Uptime: {aggregated['average_uptime_readable']}")
```

## Core Functions

### 1. Process Device Metrics

Transform raw SNMP data into structured metrics with calculated statistics.

```python
processed = processor.process_device_metrics(raw_metrics)

# Processed structure:
{
    'device_name': 'spine1',
    'ip': '172.20.20.11',
    'role': 'spine',
    'collection_timestamp': '2025-02-03 14:30:00',
    'processing_timestamp': '2025-02-03 14:30:05',
    'system': {
        'sysName': 'spine1',
        'sysDescr': 'Nokia 7250 IXR',
        'uptime': '5 days, 3 hours, 15 minutes',
        'uptime_seconds': 442500,
        'contact': 'admin@example.com',
        'location': 'Lab'
    },
    'interfaces': [...],  # List of interface statistics
    'summary': {
        'total_interfaces': 10,
        'active_interfaces': 8,
        'inactive_interfaces': 2,
        'total_in_traffic': 1234567890,
        'total_out_traffic': 9876543210,
        'total_in_traffic_readable': '1.2 GB',
        'total_out_traffic_readable': '9.2 GB',
        'total_errors': 5,
        'uptime_seconds': 442500
    },
    'success': True,
    'error': None
}
```

### 2. Aggregate Metrics

Combine metrics from multiple devices for fleet-wide analysis.

```python
aggregated = processor.aggregate_metrics(processed_list)

# Aggregated structure includes:
# - total_devices, successful_collections, failed_collections
# - total_interfaces, total_active_interfaces
# - total_traffic_in, total_traffic_out (with readable formats)
# - average_uptime
# - devices_summary (list of per-device summaries)
# - top_devices_by_traffic (top 5 devices)
# - devices_with_errors
```

### 3. Format Traffic

Convert bytes to human-readable format.

```python
processor.format_traffic(1500)          # "1.5 KB"
processor.format_traffic(2500000)       # "2.4 MB"
processor.format_traffic(1234567890)    # "1.1 GB"
processor.format_traffic(0)             # "0 B"
```

### 4. Format Uptime

Convert seconds to readable uptime string.

```python
processor.format_uptime(442500)   # "5 days, 3 hours, 15 minutes"
processor.format_uptime(9000)     # "2 hours, 30 minutes"
processor.format_uptime(120)      # "2 minutes"
```

### 5. Calculate Interface Utilization

Estimate interface utilization percentage.

```python
util = processor.calculate_interface_utilization(
    in_octets=1000000,
    out_octets=500000,
    speed=1000000000,  # 1 Gbps
    time_window=300    # 5 minutes
)

print(f"In:    {util['in_utilization']:.2f}%")
print(f"Out:   {util['out_utilization']:.2f}%")
print(f"Total: {util['total_utilization']:.2f}%")
```

## Export Functions

### Export to JSON

```python
# Export aggregated metrics
json_file = processor.export_to_json(aggregated)
print(f"Saved to: {json_file}")

# Custom filename
json_file = processor.export_to_json(aggregated, "network_metrics.json")

# Export single device
json_file = processor.export_to_json(processed)
```

### Export to CSV (Device Summary)

```python
# Export device summaries to CSV
csv_file = processor.export_to_csv(processed_list)

# CSV columns:
# Device Name, IP Address, Role, Uptime, Total Interfaces,
# Active Interfaces, Inactive Interfaces, Total In Traffic,
# Total Out Traffic, Total Errors, Status
```

### Export Interface Statistics to CSV

```python
# Export detailed interface stats for a device
csv_file = processor.export_interface_stats_csv(processed)

# CSV columns:
# Device, Interface, Index, Admin Status, Oper Status,
# Speed (bps), MTU, In Octets, Out Octets, In Packets,
# Out Packets, In Errors, Out Errors
```

## Report Generation

### Summary Report

Generate comprehensive fleet-wide summary report.

```python
report = processor.generate_summary_report(processed_list)
print(report)

# Save to file
with open('reports/summary.txt', 'w') as f:
    f.write(report)
```

**Sample Output:**
```
================================================================================
NETWORK MONITORING - SUMMARY REPORT
================================================================================
Collection Time: 2025-02-03 14:30:00

OVERVIEW
--------------------------------------------------------------------------------
  Total Devices Monitored:    4
  Successful Collections:     4
  Failed Collections:         0
  Success Rate:               100.0%

INTERFACE STATISTICS
--------------------------------------------------------------------------------
  Total Interfaces:           40
  Active Interfaces:          32
  Inactive Interfaces:        8

TRAFFIC STATISTICS
--------------------------------------------------------------------------------
  Total Inbound Traffic:      12.5 GB
  Total Outbound Traffic:     45.2 GB
  Combined Traffic:           57.7 GB
  Average Device Uptime:      3 days, 12 hours, 45 minutes
...
```

### Device Report

Generate detailed report for a single device.

```python
report = processor.generate_device_report(processed)
print(report)

# Save to file
with open(f'reports/device_{device_name}.txt', 'w') as f:
    f.write(report)
```

**Sample Output:**
```
================================================================================
DEVICE REPORT: spine1
================================================================================

DEVICE INFORMATION
--------------------------------------------------------------------------------
  Name:                spine1
  IP Address:          172.20.20.11
  Role:                spine
  Collection Time:     2025-02-03 14:30:00

SYSTEM INFORMATION
--------------------------------------------------------------------------------
  System Name:         spine1
  Description:         Nokia 7250 IXR
  Uptime:              5 days, 3 hours, 15 minutes
  Contact:             admin@example.com
  Location:            Lab

SUMMARY STATISTICS
--------------------------------------------------------------------------------
  Total Interfaces:    10
  Active Interfaces:   8
  Inactive Interfaces: 2
  Total In Traffic:    1.2 GB
  Total Out Traffic:   9.2 GB
  Total Errors:        5
...
```

## Historical Tracking

Save metrics snapshots for trend analysis.

```python
# Save device-specific history
history_file = processor.save_metrics_history(processed, device_name="spine1")

# Save aggregated history
history_file = processor.save_metrics_history(aggregated)

# Files are saved with timestamps for tracking over time
# Example: history_spine1_20250203_143000.json
```

## Running the Demo

A comprehensive demo script is provided to showcase all features:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the demo
python demo_metrics_processor.py
```

The demo will:
1. Collect metrics from all SNMP-enabled devices
2. Process and display metrics for each device
3. Aggregate fleet-wide statistics
4. Export to JSON and CSV formats
5. Generate summary and device reports
6. Save metrics history

## Integration Example

Complete workflow integrating SNMP monitoring and metrics processing:

```python
#!/usr/bin/env python3
from src.metrics_processor import MetricsProcessor
from src.snmp_monitor import SNMPMonitor
from src.utils import setup_logging, print_success

# Setup
logger = setup_logging(log_level="INFO")
processor = MetricsProcessor(output_dir="reports")
monitor = SNMPMonitor()

# Collect from all devices
print("Collecting metrics...")
raw_list = monitor.collect_all_devices(parallel=True)

# Process
print("Processing metrics...")
processed_list = [processor.process_device_metrics(m) for m in raw_list]

# Aggregate
print("Aggregating...")
aggregated = processor.aggregate_metrics(processed_list)

# Export
print("Exporting...")
processor.export_to_json(aggregated, "daily_metrics.json")
processor.export_to_csv(processed_list, "daily_devices.csv")

# Report
report = processor.generate_summary_report(processed_list)
with open('reports/daily_report.txt', 'w') as f:
    f.write(report)

# History
processor.save_metrics_history(aggregated)

print_success("Complete! Check reports/ directory for outputs.")
```

## Output Directory Structure

```
reports/
├── metrics_20250203_143000.json          # Aggregated metrics (JSON)
├── metrics_20250203_143000.csv           # Device summary (CSV)
├── interfaces_spine1_20250203_143000.csv # Interface stats (CSV)
├── network_summary_report.txt            # Summary report
├── device_report_spine1.txt              # Device report
└── history_aggregated_20250203_143000.json # Metrics history
```

## Advanced Usage

### Filter Top Interfaces by Traffic

```python
# Get top 5 interfaces by traffic
top_interfaces = processor._get_top_interfaces_by_traffic(
    processed['interfaces'],
    top_n=5
)

for idx, iface in enumerate(top_interfaces, 1):
    print(f"{idx}. {iface['name']}: {iface['total_traffic_readable']}")
```

### Custom Traffic Analysis

```python
# Calculate total traffic per device role
from collections import defaultdict

traffic_by_role = defaultdict(lambda: {'in': 0, 'out': 0})

for device in processed_list:
    if device['success']:
        role = device.get('role', 'unknown')
        traffic_by_role[role]['in'] += device['summary']['total_in_traffic']
        traffic_by_role[role]['out'] += device['summary']['total_out_traffic']

for role, traffic in traffic_by_role.items():
    total = traffic['in'] + traffic['out']
    print(f"{role}: {processor.format_traffic(total)}")
```

### Monitoring Alerts

```python
# Check for devices with high error rates
ERROR_THRESHOLD = 100

for device in processed_list:
    if device['success']:
        errors = device['summary']['total_errors']
        if errors > ERROR_THRESHOLD:
            print(f"ALERT: {device['device_name']} has {errors} errors!")
```

## API Reference

See the module docstrings for complete API documentation:

```python
help(MetricsProcessor)
help(MetricsProcessor.process_device_metrics)
help(MetricsProcessor.aggregate_metrics)
# etc.
```

## Troubleshooting

### No devices found
- Ensure devices have `snmp_enabled: true` in `inventory/devices.yaml`
- Check SNMP connectivity with SNMPMonitor first

### Export failures
- Verify `reports/` directory exists and is writable
- Check disk space

### Import errors
- Activate virtual environment: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

## Best Practices

1. **Regular Collection**: Schedule metrics collection at regular intervals for trending
2. **Historical Tracking**: Use `save_metrics_history()` to build time-series data
3. **Error Monitoring**: Check `devices_with_errors` in aggregated results
4. **Export Strategy**: Use JSON for programmatic access, CSV for spreadsheets
5. **Reports**: Generate summary reports for daily/weekly reviews

## Next Steps

- Integrate with visualization tools (Grafana, etc.)
- Build trend analysis from historical data
- Create automated alerting based on thresholds
- Add custom metrics calculations for your environment
