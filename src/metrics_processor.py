import json
import csv
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import statistics

from src.utils import (
    get_logger,
    get_timestamp,
    get_human_timestamp,
    ensure_directory,
    safe_write_file,
    print_separator
)

try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False


class MetricsProcessor:
    """
    Process and analyze SNMP metrics from network devices.

    This class provides comprehensive metrics processing capabilities including:
    - Processing raw SNMP data into structured metrics
    - Calculating derived metrics (utilization, rates, totals)
    - Aggregating metrics across multiple devices
    - Exporting to multiple formats (JSON, CSV)
    - Generating human-readable reports
    - Historical metrics tracking

    Attributes:
        output_dir (str): Directory for saving reports and exports
        logger (logging.Logger): Logger instance for this module
    """

    def __init__(self, output_dir: str = "reports") -> None:
        """
        Initialize MetricsProcessor.

        Args:
            output_dir: Directory for saving reports (default: "reports")

        Example:
            processor = MetricsProcessor(output_dir="reports")
            processor = MetricsProcessor(output_dir="output/metrics")
        """
        self.output_dir = output_dir
        self.logger = get_logger(__name__)

        # Create output directory if it doesn't exist
        if not ensure_directory(self.output_dir):
            self.logger.warning(f"Failed to create output directory: {self.output_dir}")

        self.logger.info(f"MetricsProcessor initialized - Output dir: {self.output_dir}")

    def process_device_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and enhance raw metrics from a single device.

        Takes raw metrics from SNMPMonitor.collect_device_metrics() and processes
        them into a structured format with calculated statistics and summaries.

        Args:
            raw_metrics: Raw metrics dict from SNMPMonitor.collect_device_metrics()

        Returns:
            Processed metrics dictionary with:
                - device_name: str
                - ip: str
                - role: str (if available)
                - collection_timestamp: str
                - processing_timestamp: str
                - system: dict (processed system info)
                - interfaces: list (processed interface data)
                - summary: dict (aggregated stats)
                - success: bool
                - error: str or None

        Example:
            raw = monitor.collect_device_metrics(device)
            processed = processor.process_device_metrics(raw)

            if processed['success']:
                print(f"Device: {processed['device_name']}")
                print(f"Active Interfaces: {processed['summary']['active_interfaces']}")
                print(f"Total Traffic: {processed['summary']['total_in_traffic_readable']}")
        """
        device_name = raw_metrics.get('device_name', 'unknown')
        ip = raw_metrics.get('ip', 'unknown')

        self.logger.debug(f"Processing metrics for {device_name} ({ip})")

        # Check if raw metrics collection was successful
        if not raw_metrics.get('success', False):
            error = raw_metrics.get('error', 'Unknown error during collection')
            self.logger.warning(f"{device_name}: Cannot process - collection failed: {error}")
            return {
                'device_name': device_name,
                'ip': ip,
                'role': None,
                'collection_timestamp': raw_metrics.get('collection_time', get_human_timestamp()),
                'processing_timestamp': get_human_timestamp(),
                'system': {},
                'interfaces': [],
                'summary': {},
                'success': False,
                'error': f"Collection failed: {error}"
            }

        # Extract system information
        system_info = raw_metrics.get('system_info', {})
        interfaces = raw_metrics.get('interfaces', [])

        # Process system info
        processed_system = {
            'sysName': system_info.get('sysName', 'N/A'),
            'sysDescr': system_info.get('sysDescr', 'N/A'),
            'uptime': system_info.get('sysUpTime_readable', 'N/A'),
            'uptime_seconds': system_info.get('sysUpTime', 0),
            'contact': system_info.get('sysContact', 'N/A'),
            'location': system_info.get('sysLocation', 'N/A'),
            'object_id': system_info.get('sysObjectID', 'N/A')
        }

        # Process interface data
        processed_interfaces = []
        for iface in interfaces:
            processed_iface = {
                'index': iface.get('index', 0),
                'name': iface.get('name', 'N/A'),
                'type': iface.get('type', 0),
                'admin_status': iface.get('admin_status', 'unknown'),
                'oper_status': iface.get('oper_status', 'unknown'),
                'speed': iface.get('speed', 0),
                'mtu': iface.get('mtu', 0),
                'mac_address': iface.get('mac_address', 'N/A'),
                'in_octets': iface.get('in_octets', 0),
                'in_packets': iface.get('in_packets', 0),
                'in_errors': iface.get('in_errors', 0),
                'out_octets': iface.get('out_octets', 0),
                'out_packets': iface.get('out_packets', 0),
                'out_errors': iface.get('out_errors', 0),
                'total_traffic': iface.get('in_octets', 0) + iface.get('out_octets', 0)
            }
            processed_interfaces.append(processed_iface)

        # Calculate summary statistics
        total_in, total_out = self._calculate_total_traffic(processed_interfaces)
        status_counts = self._count_interface_status(processed_interfaces)
        total_errors = sum(
            iface.get('in_errors', 0) + iface.get('out_errors', 0)
            for iface in processed_interfaces
        )

        summary = {
            'total_interfaces': len(processed_interfaces),
            'active_interfaces': status_counts.get('up', 0),
            'inactive_interfaces': status_counts.get('down', 0) + status_counts.get('other', 0),
            'total_in_traffic': total_in,
            'total_out_traffic': total_out,
            'total_in_traffic_readable': self.format_traffic(total_in),
            'total_out_traffic_readable': self.format_traffic(total_out),
            'total_errors': total_errors,
            'uptime_seconds': processed_system['uptime_seconds']
        }

        # Build result
        result = {
            'device_name': device_name,
            'ip': ip,
            'role': None,  # Will be populated if available in device info
            'collection_timestamp': raw_metrics.get('collection_time', get_human_timestamp()),
            'processing_timestamp': get_human_timestamp(),
            'system': processed_system,
            'interfaces': processed_interfaces,
            'summary': summary,
            'success': True,
            'error': None
        }

        self.logger.info(
            f"{device_name}: Processed {len(processed_interfaces)} interfaces, "
            f"{summary['active_interfaces']} active"
        )

        return result

    def aggregate_metrics(self, metrics_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate metrics across multiple devices.

        Calculates fleet-wide statistics including totals, averages, and
        identifies top performers and problem devices.

        Args:
            metrics_list: List of processed metrics dicts from process_device_metrics()

        Returns:
            Aggregated metrics dictionary with:
                - total_devices: int
                - successful_collections: int
                - failed_collections: int
                - total_interfaces: int
                - total_active_interfaces: int
                - total_traffic_in: int
                - total_traffic_out: int
                - average_uptime: float
                - devices_summary: list (per-device summary)
                - top_devices_by_traffic: list (top 5)
                - devices_with_errors: list
                - collection_timestamp: str

        Example:
            processed_list = [processor.process_device_metrics(m) for m in raw_list]
            aggregated = processor.aggregate_metrics(processed_list)

            print(f"Total Devices: {aggregated['total_devices']}")
            print(f"Total Traffic: {aggregated['total_traffic_in'] + aggregated['total_traffic_out']}")
        """
        self.logger.info(f"Aggregating metrics from {len(metrics_list)} devices")

        if not metrics_list:
            self.logger.warning("No metrics to aggregate")
            return {
                'total_devices': 0,
                'successful_collections': 0,
                'failed_collections': 0,
                'total_interfaces': 0,
                'total_active_interfaces': 0,
                'total_traffic_in': 0,
                'total_traffic_out': 0,
                'average_uptime': 0.0,
                'devices_summary': [],
                'top_devices_by_traffic': [],
                'devices_with_errors': [],
                'collection_timestamp': get_human_timestamp()
            }

        # Initialize counters
        successful = 0
        failed = 0
        total_interfaces = 0
        total_active_interfaces = 0
        total_traffic_in = 0
        total_traffic_out = 0
        uptime_values = []
        devices_summary = []
        devices_with_errors = []

        # Process each device
        for metrics in metrics_list:
            device_name = metrics.get('device_name', 'unknown')

            if metrics.get('success', False):
                successful += 1
                summary = metrics.get('summary', {})

                # Accumulate totals
                total_interfaces += summary.get('total_interfaces', 0)
                total_active_interfaces += summary.get('active_interfaces', 0)
                total_traffic_in += summary.get('total_in_traffic', 0)
                total_traffic_out += summary.get('total_out_traffic', 0)

                # Collect uptime
                uptime = summary.get('uptime_seconds', 0)
                if uptime > 0:
                    uptime_values.append(uptime)

                # Device summary
                device_summary = {
                    'device_name': device_name,
                    'ip': metrics.get('ip', 'unknown'),
                    'role': metrics.get('role'),
                    'interfaces': summary.get('total_interfaces', 0),
                    'active_interfaces': summary.get('active_interfaces', 0),
                    'total_traffic': summary.get('total_in_traffic', 0) + summary.get('total_out_traffic', 0),
                    'total_traffic_readable': self.format_traffic(
                        summary.get('total_in_traffic', 0) + summary.get('total_out_traffic', 0)
                    ),
                    'errors': summary.get('total_errors', 0),
                    'uptime_seconds': uptime
                }
                devices_summary.append(device_summary)

                # Track devices with errors
                if summary.get('total_errors', 0) > 0:
                    devices_with_errors.append({
                        'device_name': device_name,
                        'ip': metrics.get('ip', 'unknown'),
                        'error_count': summary.get('total_errors', 0)
                    })
            else:
                failed += 1
                devices_summary.append({
                    'device_name': device_name,
                    'ip': metrics.get('ip', 'unknown'),
                    'role': metrics.get('role'),
                    'status': 'failed',
                    'error': metrics.get('error', 'Unknown error')
                })

        # Calculate average uptime
        average_uptime = statistics.mean(uptime_values) if uptime_values else 0.0

        # Find top devices by traffic
        top_devices = sorted(
            [d for d in devices_summary if d.get('total_traffic', 0) > 0],
            key=lambda x: x.get('total_traffic', 0),
            reverse=True
        )[:5]

        # Build aggregated result
        result = {
            'total_devices': len(metrics_list),
            'successful_collections': successful,
            'failed_collections': failed,
            'total_interfaces': total_interfaces,
            'total_active_interfaces': total_active_interfaces,
            'total_traffic_in': total_traffic_in,
            'total_traffic_out': total_traffic_out,
            'total_traffic_in_readable': self.format_traffic(total_traffic_in),
            'total_traffic_out_readable': self.format_traffic(total_traffic_out),
            'average_uptime': average_uptime,
            'average_uptime_readable': self.format_uptime(int(average_uptime)),
            'devices_summary': devices_summary,
            'top_devices_by_traffic': top_devices,
            'devices_with_errors': devices_with_errors,
            'collection_timestamp': get_human_timestamp()
        }

        self.logger.info(
            f"Aggregation complete - {successful} successful, {failed} failed, "
            f"Total traffic: {self.format_traffic(total_traffic_in + total_traffic_out)}"
        )

        return result

    def format_traffic(self, bytes_value: int) -> str:
        """
        Convert bytes to human-readable format.

        Automatically selects appropriate unit (B, KB, MB, GB, TB).

        Args:
            bytes_value: Traffic value in bytes

        Returns:
            Formatted string with appropriate unit

        Example:
            processor.format_traffic(1500)         # "1.5 KB"
            processor.format_traffic(2500000)      # "2.4 MB"
            processor.format_traffic(1234567890)   # "1.1 GB"
            processor.format_traffic(0)            # "0 B"
        """
        if bytes_value < 0:
            return "0 B"

        if bytes_value == 0:
            return "0 B"

        # Define units
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        unit_index = 0
        value = float(bytes_value)

        # Find appropriate unit
        while value >= 1024.0 and unit_index < len(units) - 1:
            value /= 1024.0
            unit_index += 1

        # Format based on size
        if unit_index == 0:
            # Bytes - no decimal
            return f"{int(value)} {units[unit_index]}"
        else:
            # Larger units - 1 decimal place
            return f"{value:.1f} {units[unit_index]}"

    def format_uptime(self, seconds: int) -> str:
        """
        Convert seconds to human-readable uptime.

        Formats uptime as "X days, Y hours, Z minutes".

        Args:
            seconds: Uptime in seconds

        Returns:
            Formatted uptime string

        Example:
            processor.format_uptime(442500)    # "5 days, 3 hours, 15 minutes"
            processor.format_uptime(9000)      # "2 hours, 30 minutes"
            processor.format_uptime(120)       # "2 minutes"
        """
        if seconds <= 0:
            return "0 seconds"

        # Calculate time components
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        # Build readable string
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if not parts and secs > 0:
            # Only show seconds if nothing else to show
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")

        return ", ".join(parts) if parts else "0 seconds"

    def calculate_interface_utilization(
        self,
        in_octets: int,
        out_octets: int,
        speed: int,
        time_window: int = 300
    ) -> Dict[str, float]:
        """
        Calculate interface utilization percentage.

        Note: This is a simplified calculation. Real utilization requires
        delta measurements over time. This provides an estimate based on
        current counter values and assumed time window.

        Args:
            in_octets: Incoming bytes
            out_octets: Outgoing bytes
            speed: Interface speed in bits/sec
            time_window: Measurement window in seconds (default: 300 = 5 min)

        Returns:
            Dictionary with:
                - in_utilization: float (percentage)
                - out_utilization: float (percentage)
                - total_utilization: float (percentage)

        Example:
            util = processor.calculate_interface_utilization(
                in_octets=1000000,
                out_octets=500000,
                speed=1000000000,
                time_window=300
            )
            print(f"In: {util['in_utilization']:.2f}%")
            print(f"Out: {util['out_utilization']:.2f}%")
        """
        # Handle invalid inputs
        if speed <= 0 or time_window <= 0:
            return {
                'in_utilization': 0.0,
                'out_utilization': 0.0,
                'total_utilization': 0.0
            }

        # Convert octets to bits
        in_bits = in_octets * 8
        out_bits = out_octets * 8

        # Calculate bits per second (average over time window)
        in_bps = in_bits / time_window
        out_bps = out_bits / time_window

        # Calculate utilization percentage
        in_utilization = (in_bps / speed) * 100 if speed > 0 else 0.0
        out_utilization = (out_bps / speed) * 100 if speed > 0 else 0.0
        total_utilization = ((in_bps + out_bps) / (speed * 2)) * 100 if speed > 0 else 0.0

        # Cap at 100%
        in_utilization = min(in_utilization, 100.0)
        out_utilization = min(out_utilization, 100.0)
        total_utilization = min(total_utilization, 100.0)

        return {
            'in_utilization': round(in_utilization, 2),
            'out_utilization': round(out_utilization, 2),
            'total_utilization': round(total_utilization, 2)
        }

    def export_to_json(
        self,
        metrics: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """
        Export metrics to JSON file.

        Saves metrics in pretty-printed JSON format for readability.

        Args:
            metrics: Metrics dictionary to export
            filename: Output filename (auto-generated if None)

        Returns:
            Full filepath to saved JSON file

        Example:
            aggregated = processor.aggregate_metrics(processed_list)
            filepath = processor.export_to_json(aggregated)
            print(f"Saved to: {filepath}")

            # Custom filename
            filepath = processor.export_to_json(aggregated, "network_metrics.json")
        """
        # Generate filename if not provided
        if filename is None:
            timestamp = get_timestamp()
            filename = f"metrics_{timestamp}.json"

        # Ensure .json extension
        if not filename.endswith('.json'):
            filename += '.json'

        filepath = os.path.join(self.output_dir, filename)

        try:
            # Prepare metrics for JSON serialization
            clean_metrics = self._format_metrics_for_json(metrics)

            # Write JSON with pretty printing
            json_content = json.dumps(clean_metrics, indent=2, ensure_ascii=False)

            if safe_write_file(filepath, json_content):
                self.logger.info(f"Metrics exported to JSON: {filepath}")
                return filepath
            else:
                self.logger.error(f"Failed to write JSON file: {filepath}")
                return ""

        except Exception as e:
            self.logger.error(f"Error exporting to JSON: {e}")
            return ""

    def export_to_csv(
        self,
        metrics_list: List[Dict[str, Any]],
        filename: Optional[str] = None
    ) -> str:
        """
        Export device metrics to CSV file.

        Creates a CSV with device summary information including name, IP,
        role, uptime, interface counts, traffic totals, and errors.

        Args:
            metrics_list: List of processed device metrics
            filename: Output filename (auto-generated if None)

        Returns:
            Full filepath to saved CSV file

        Example:
            processed_list = [processor.process_device_metrics(m) for m in raw_list]
            filepath = processor.export_to_csv(processed_list)
            print(f"Saved to: {filepath}")
        """
        # Generate filename if not provided
        if filename is None:
            timestamp = get_timestamp()
            filename = f"metrics_{timestamp}.csv"

        # Ensure .csv extension
        if not filename.endswith('.csv'):
            filename += '.csv'

        filepath = os.path.join(self.output_dir, filename)

        try:
            # Prepare CSV data
            headers = [
                'Device Name', 'IP Address', 'Role', 'Uptime',
                'Total Interfaces', 'Active Interfaces', 'Inactive Interfaces',
                'Total In Traffic', 'Total Out Traffic', 'Total Errors', 'Status'
            ]

            rows = []
            for metrics in metrics_list:
                if metrics.get('success', False):
                    summary = metrics.get('summary', {})
                    row = [
                        metrics.get('device_name', 'N/A'),
                        metrics.get('ip', 'N/A'),
                        metrics.get('role', 'N/A'),
                        self.format_uptime(summary.get('uptime_seconds', 0)),
                        summary.get('total_interfaces', 0),
                        summary.get('active_interfaces', 0),
                        summary.get('inactive_interfaces', 0),
                        summary.get('total_in_traffic_readable', '0 B'),
                        summary.get('total_out_traffic_readable', '0 B'),
                        summary.get('total_errors', 0),
                        'Success'
                    ]
                else:
                    row = [
                        metrics.get('device_name', 'N/A'),
                        metrics.get('ip', 'N/A'),
                        metrics.get('role', 'N/A'),
                        'N/A', 0, 0, 0, 'N/A', 'N/A', 0,
                        f"Failed: {metrics.get('error', 'Unknown')}"
                    ]
                rows.append(row)

            # Write CSV
            csv_content = []
            csv_content.append(','.join(f'"{h}"' for h in headers))
            for row in rows:
                csv_content.append(','.join(f'"{str(v)}"' for v in row))

            csv_text = '\n'.join(csv_content) + '\n'

            if safe_write_file(filepath, csv_text):
                self.logger.info(f"Metrics exported to CSV: {filepath}")
                return filepath
            else:
                self.logger.error(f"Failed to write CSV file: {filepath}")
                return ""

        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")
            return ""

    def export_interface_stats_csv(
        self,
        device_metrics: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """
        Export interface statistics to CSV.

        Creates detailed CSV with per-interface statistics including status,
        speed, MTU, traffic counters, and error counters.

        Args:
            device_metrics: Processed device metrics dict
            filename: Output filename (auto-generated if None)

        Returns:
            Full filepath to saved CSV file

        Example:
            processed = processor.process_device_metrics(raw_metrics)
            filepath = processor.export_interface_stats_csv(processed)
            print(f"Interface stats saved to: {filepath}")
        """
        device_name = device_metrics.get('device_name', 'unknown')

        # Generate filename if not provided
        if filename is None:
            timestamp = get_timestamp()
            filename = f"interfaces_{device_name}_{timestamp}.csv"

        # Ensure .csv extension
        if not filename.endswith('.csv'):
            filename += '.csv'

        filepath = os.path.join(self.output_dir, filename)

        try:
            # Prepare CSV data
            headers = [
                'Device', 'Interface', 'Index', 'Admin Status', 'Oper Status',
                'Speed (bps)', 'MTU', 'In Octets', 'Out Octets',
                'In Packets', 'Out Packets', 'In Errors', 'Out Errors'
            ]

            rows = []
            interfaces = device_metrics.get('interfaces', [])

            for iface in interfaces:
                row = [
                    device_name,
                    iface.get('name', 'N/A'),
                    iface.get('index', 0),
                    iface.get('admin_status', 'unknown'),
                    iface.get('oper_status', 'unknown'),
                    iface.get('speed', 0),
                    iface.get('mtu', 0),
                    iface.get('in_octets', 0),
                    iface.get('out_octets', 0),
                    iface.get('in_packets', 0),
                    iface.get('out_packets', 0),
                    iface.get('in_errors', 0),
                    iface.get('out_errors', 0)
                ]
                rows.append(row)

            # Write CSV
            csv_content = []
            csv_content.append(','.join(f'"{h}"' for h in headers))
            for row in rows:
                csv_content.append(','.join(f'"{str(v)}"' for v in row))

            csv_text = '\n'.join(csv_content) + '\n'

            if safe_write_file(filepath, csv_text):
                self.logger.info(f"Interface stats exported to CSV: {filepath}")
                return filepath
            else:
                self.logger.error(f"Failed to write CSV file: {filepath}")
                return ""

        except Exception as e:
            self.logger.error(f"Error exporting interface stats to CSV: {e}")
            return ""

    def generate_summary_report(self, metrics_list: List[Dict[str, Any]]) -> str:
        """
        Generate text summary report.

        Creates human-readable summary report with collection statistics,
        traffic totals, top devices, and error summary.

        Args:
            metrics_list: List of processed device metrics

        Returns:
            Formatted report string (ready to print or save)

        Example:
            processed_list = [processor.process_device_metrics(m) for m in raw_list]
            report = processor.generate_summary_report(processed_list)
            print(report)

            # Save to file
            with open('report.txt', 'w') as f:
                f.write(report)
        """
        # Aggregate metrics
        aggregated = self.aggregate_metrics(metrics_list)

        # Build report
        lines = []
        lines.append("=" * 80)
        lines.append("NETWORK MONITORING - SUMMARY REPORT")
        lines.append("=" * 80)
        lines.append(f"Collection Time: {aggregated['collection_timestamp']}")
        lines.append("")

        # Overview
        lines.append("OVERVIEW")
        lines.append("-" * 80)
        lines.append(f"  Total Devices Monitored:    {aggregated['total_devices']}")
        lines.append(f"  Successful Collections:     {aggregated['successful_collections']}")
        lines.append(f"  Failed Collections:         {aggregated['failed_collections']}")
        lines.append(f"  Success Rate:               {aggregated['successful_collections'] / aggregated['total_devices'] * 100:.1f}%" if aggregated['total_devices'] > 0 else "  Success Rate:               N/A")
        lines.append("")

        # Interface Statistics
        lines.append("INTERFACE STATISTICS")
        lines.append("-" * 80)
        lines.append(f"  Total Interfaces:           {aggregated['total_interfaces']}")
        lines.append(f"  Active Interfaces:          {aggregated['total_active_interfaces']}")
        lines.append(f"  Inactive Interfaces:        {aggregated['total_interfaces'] - aggregated['total_active_interfaces']}")
        lines.append("")

        # Traffic Statistics
        lines.append("TRAFFIC STATISTICS")
        lines.append("-" * 80)
        lines.append(f"  Total Inbound Traffic:      {aggregated['total_traffic_in_readable']}")
        lines.append(f"  Total Outbound Traffic:     {aggregated['total_traffic_out_readable']}")
        lines.append(f"  Combined Traffic:           {self.format_traffic(aggregated['total_traffic_in'] + aggregated['total_traffic_out'])}")
        lines.append(f"  Average Device Uptime:      {aggregated['average_uptime_readable']}")
        lines.append("")

        # Top Devices by Traffic
        if aggregated['top_devices_by_traffic']:
            lines.append("TOP DEVICES BY TRAFFIC")
            lines.append("-" * 80)
            for idx, device in enumerate(aggregated['top_devices_by_traffic'], 1):
                lines.append(
                    f"  {idx}. {device['device_name']} ({device['ip']}): "
                    f"{device['total_traffic_readable']}"
                )
            lines.append("")

        # Devices with Errors
        if aggregated['devices_with_errors']:
            lines.append("DEVICES WITH ERRORS")
            lines.append("-" * 80)
            for device in aggregated['devices_with_errors']:
                lines.append(
                    f"  {device['device_name']} ({device['ip']}): "
                    f"{device['error_count']:,} errors"
                )
            lines.append("")

        # Per-Device Summary
        lines.append("PER-DEVICE SUMMARY")
        lines.append("-" * 80)

        if TABULATE_AVAILABLE:
            # Use tabulate for nice formatting
            table_data = []
            for device in aggregated['devices_summary']:
                if device.get('status') == 'failed':
                    table_data.append([
                        device['device_name'],
                        device['ip'],
                        'FAILED',
                        '-',
                        '-',
                        device.get('error', 'Unknown')[:30]
                    ])
                else:
                    table_data.append([
                        device['device_name'],
                        device['ip'],
                        device.get('interfaces', 0),
                        device.get('active_interfaces', 0),
                        device.get('total_traffic_readable', 'N/A'),
                        device.get('errors', 0)
                    ])

            headers = ['Device', 'IP', 'Interfaces', 'Active', 'Traffic', 'Errors']
            lines.append(tabulate(table_data, headers=headers, tablefmt='simple'))
        else:
            # Fallback to simple formatting
            for device in aggregated['devices_summary']:
                if device.get('status') == 'failed':
                    lines.append(f"  {device['device_name']} ({device['ip']}): FAILED")
                else:
                    lines.append(
                        f"  {device['device_name']} ({device['ip']}): "
                        f"{device.get('interfaces', 0)} interfaces, "
                        f"{device.get('total_traffic_readable', 'N/A')} traffic"
                    )

        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)

    def generate_device_report(self, device_metrics: Dict[str, Any]) -> str:
        """
        Generate detailed report for single device.

        Creates comprehensive report with device information, system details,
        interface summary table, and traffic/error statistics.

        Args:
            device_metrics: Processed device metrics dict

        Returns:
            Formatted report string

        Example:
            processed = processor.process_device_metrics(raw_metrics)
            report = processor.generate_device_report(processed)
            print(report)
        """
        device_name = device_metrics.get('device_name', 'unknown')

        # Build report
        lines = []
        lines.append("=" * 80)
        lines.append(f"DEVICE REPORT: {device_name}")
        lines.append("=" * 80)
        lines.append("")

        # Device Information
        lines.append("DEVICE INFORMATION")
        lines.append("-" * 80)
        lines.append(f"  Name:                {device_name}")
        lines.append(f"  IP Address:          {device_metrics.get('ip', 'N/A')}")
        lines.append(f"  Role:                {device_metrics.get('role', 'N/A')}")
        lines.append(f"  Collection Time:     {device_metrics.get('collection_timestamp', 'N/A')}")
        lines.append("")

        # System Information
        system = device_metrics.get('system', {})
        lines.append("SYSTEM INFORMATION")
        lines.append("-" * 80)
        lines.append(f"  System Name:         {system.get('sysName', 'N/A')}")
        lines.append(f"  Description:         {system.get('sysDescr', 'N/A')[:60]}")
        lines.append(f"  Uptime:              {system.get('uptime', 'N/A')}")
        lines.append(f"  Contact:             {system.get('contact', 'N/A')}")
        lines.append(f"  Location:            {system.get('location', 'N/A')}")
        lines.append("")

        # Summary Statistics
        summary = device_metrics.get('summary', {})
        lines.append("SUMMARY STATISTICS")
        lines.append("-" * 80)
        lines.append(f"  Total Interfaces:    {summary.get('total_interfaces', 0)}")
        lines.append(f"  Active Interfaces:   {summary.get('active_interfaces', 0)}")
        lines.append(f"  Inactive Interfaces: {summary.get('inactive_interfaces', 0)}")
        lines.append(f"  Total In Traffic:    {summary.get('total_in_traffic_readable', '0 B')}")
        lines.append(f"  Total Out Traffic:   {summary.get('total_out_traffic_readable', '0 B')}")
        lines.append(f"  Total Errors:        {summary.get('total_errors', 0)}")
        lines.append("")

        # Interface Details
        interfaces = device_metrics.get('interfaces', [])
        if interfaces:
            lines.append("INTERFACE DETAILS")
            lines.append("-" * 80)

            if TABULATE_AVAILABLE:
                # Use tabulate for nice table
                table_data = []
                for iface in interfaces:
                    table_data.append([
                        iface.get('name', 'N/A'),
                        iface.get('admin_status', 'unknown'),
                        iface.get('oper_status', 'unknown'),
                        self.format_traffic(iface.get('speed', 0)) if iface.get('speed', 0) > 0 else 'N/A',
                        self.format_traffic(iface.get('in_octets', 0)),
                        self.format_traffic(iface.get('out_octets', 0)),
                        iface.get('in_errors', 0) + iface.get('out_errors', 0)
                    ])

                headers = ['Interface', 'Admin', 'Oper', 'Speed', 'In', 'Out', 'Errors']
                lines.append(tabulate(table_data, headers=headers, tablefmt='simple'))
            else:
                # Fallback to simple formatting
                for iface in interfaces:
                    lines.append(
                        f"  {iface.get('name', 'N/A')}: {iface.get('oper_status', 'unknown')} "
                        f"(In: {self.format_traffic(iface.get('in_octets', 0))}, "
                        f"Out: {self.format_traffic(iface.get('out_octets', 0))})"
                    )

        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)

    def save_metrics_history(
        self,
        metrics: Dict[str, Any],
        device_name: Optional[str] = None
    ) -> str:
        """
        Save metrics to timestamped file for historical tracking.

        Enables trend analysis by saving metrics snapshots over time.
        Creates separate history files for each device or aggregated data.

        Args:
            metrics: Metrics dictionary to save
            device_name: Device name for device-specific history (None for aggregated)

        Returns:
            Full filepath to saved history file

        Example:
            # Save device-specific history
            processed = processor.process_device_metrics(raw_metrics)
            filepath = processor.save_metrics_history(processed, device_name="spine1")

            # Save aggregated history
            aggregated = processor.aggregate_metrics(processed_list)
            filepath = processor.save_metrics_history(aggregated)
        """
        timestamp = get_timestamp()

        # Build filename
        if device_name:
            filename = f"history_{device_name}_{timestamp}.json"
        else:
            filename = f"history_aggregated_{timestamp}.json"

        filepath = os.path.join(self.output_dir, filename)

        try:
            # Prepare metrics for JSON
            clean_metrics = self._format_metrics_for_json(metrics)
            clean_metrics['saved_timestamp'] = get_human_timestamp()

            # Write JSON
            json_content = json.dumps(clean_metrics, indent=2, ensure_ascii=False)

            if safe_write_file(filepath, json_content):
                self.logger.info(f"Metrics history saved: {filepath}")
                return filepath
            else:
                self.logger.error(f"Failed to save metrics history: {filepath}")
                return ""

        except Exception as e:
            self.logger.error(f"Error saving metrics history: {e}")
            return ""

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _calculate_total_traffic(
        self,
        interfaces: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """
        Sum traffic across all interfaces.

        Args:
            interfaces: List of interface dictionaries

        Returns:
            Tuple of (total_in_octets, total_out_octets)
        """
        total_in = sum(iface.get('in_octets', 0) for iface in interfaces)
        total_out = sum(iface.get('out_octets', 0) for iface in interfaces)
        return total_in, total_out

    def _count_interface_status(
        self,
        interfaces: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Count interfaces by operational status.

        Args:
            interfaces: List of interface dictionaries

        Returns:
            Dictionary with counts: {'up': count, 'down': count, 'other': count}
        """
        counts = {'up': 0, 'down': 0, 'other': 0}

        for iface in interfaces:
            status = iface.get('oper_status', 'unknown').lower()
            if status == 'up':
                counts['up'] += 1
            elif status == 'down':
                counts['down'] += 1
            else:
                counts['other'] += 1

        return counts

    def _get_top_interfaces_by_traffic(
        self,
        interfaces: List[Dict[str, Any]],
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get top N interfaces by total traffic.

        Args:
            interfaces: List of interface dictionaries
            top_n: Number of top interfaces to return

        Returns:
            List of top interfaces with traffic info
        """
        # Sort by total traffic
        sorted_interfaces = sorted(
            interfaces,
            key=lambda x: x.get('total_traffic', 0),
            reverse=True
        )

        # Return top N
        top_interfaces = []
        for iface in sorted_interfaces[:top_n]:
            top_interfaces.append({
                'name': iface.get('name', 'N/A'),
                'total_traffic': iface.get('total_traffic', 0),
                'total_traffic_readable': self.format_traffic(iface.get('total_traffic', 0)),
                'in_octets': iface.get('in_octets', 0),
                'out_octets': iface.get('out_octets', 0)
            })

        return top_interfaces

    def _format_metrics_for_json(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare metrics dictionary for JSON serialization.

        Ensures all values are JSON-serializable by converting special types.

        Args:
            metrics: Metrics dictionary

        Returns:
            Clean dictionary ready for JSON serialization
        """
        # Create deep copy to avoid modifying original
        import copy
        clean = copy.deepcopy(metrics)

        # Recursively convert non-serializable types
        def clean_value(obj):
            if isinstance(obj, dict):
                return {k: clean_value(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_value(item) for item in obj]
            elif isinstance(obj, (datetime,)):
                return obj.isoformat()
            elif isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            else:
                # Convert other types to string
                return str(obj)

        return clean_value(clean)

    def _format_timestamp(self, timestamp_str: Optional[str] = None) -> str:
        """
        Format timestamp consistently.

        Args:
            timestamp_str: Timestamp string to format (None = current time)

        Returns:
            Formatted timestamp string: "YYYY-MM-DD HH:MM:SS"
        """
        if timestamp_str is None:
            return get_human_timestamp()
        return timestamp_str


# ============================================================================
# MODULE TESTING AND EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    """
    Example usage and testing of MetricsProcessor class.
    Run this script directly to test metrics processing functionality.
    """
    from src.utils import setup_logging, print_success, print_error, print_info
    from src.snmp_monitor import SNMPMonitor

    # Setup logging
    logger = setup_logging(log_level="INFO")

    print_separator()
    print("Metrics Processor - Example Usage")
    print_separator()

    try:
        # Initialize
        print_info("Initializing Metrics Processor and SNMP Monitor...")
        processor = MetricsProcessor(output_dir="reports")
        monitor = SNMPMonitor(
            inventory_path="inventory/devices.yaml",
            default_community="public",
            timeout=5,
            retries=2
        )

        # Get SNMP-enabled devices
        devices = monitor.inventory_loader.get_snmp_enabled_devices()
        print_info(f"Found {len(devices)} SNMP-enabled devices")

        if not devices:
            print_error("No SNMP-enabled devices found in inventory")
            sys.exit(1)

        # Example 1: Process single device
        print_separator()
        print_info("Example 1: Single Device Processing")
        print_separator()

        device = devices[0]
        print(f"Collecting metrics from: {device['name']} ({device['ip']})")

        raw_metrics = monitor.collect_device_metrics(device)
        processed = processor.process_device_metrics(raw_metrics)

        if processed['success']:
            print_success(f"Metrics processed successfully")
            print(f"\nDevice: {processed['device_name']}")
            print(f"Uptime: {processor.format_uptime(processed['summary']['uptime_seconds'])}")
            print(f"Interfaces: {processed['summary']['total_interfaces']} "
                  f"({processed['summary']['active_interfaces']} active)")
            print(f"Total In: {processed['summary']['total_in_traffic_readable']}")
            print(f"Total Out: {processed['summary']['total_out_traffic_readable']}")

            # Generate device report
            print("\nDetailed Device Report:")
            print(processor.generate_device_report(processed))
        else:
            print_error(f"Failed: {processed['error']}")

        # Example 2: Multiple devices
        print_separator()
        print_info("Example 2: Multi-Device Processing and Aggregation")
        print_separator()

        # Collect from multiple devices
        raw_list = monitor.collect_multiple_devices(devices[:3], parallel=True)
        print_success(f"Collected from {len(raw_list)} devices")

        # Process all
        processed_list = [processor.process_device_metrics(m) for m in raw_list]
        print_success(f"Processed {len(processed_list)} devices")

        # Aggregate
        aggregated = processor.aggregate_metrics(processed_list)
        print_success("Metrics aggregated")

        print(f"\nAggregated Results:")
        print(f"  Total Devices: {aggregated['total_devices']}")
        print(f"  Successful: {aggregated['successful_collections']}")
        print(f"  Failed: {aggregated['failed_collections']}")
        print(f"  Total Interfaces: {aggregated['total_interfaces']}")
        print(f"  Total Traffic: {processor.format_traffic(aggregated['total_traffic_in'] + aggregated['total_traffic_out'])}")

        # Example 3: Export to files
        print_separator()
        print_info("Example 3: Exporting Metrics")
        print_separator()

        # Export to JSON
        json_file = processor.export_to_json(aggregated, "test_aggregated.json")
        if json_file:
            print_success(f"JSON exported: {json_file}")

        # Export to CSV
        csv_file = processor.export_to_csv(processed_list, "test_devices.csv")
        if csv_file:
            print_success(f"CSV exported: {csv_file}")

        # Export interface stats
        if processed_list and processed_list[0]['success']:
            iface_csv = processor.export_interface_stats_csv(
                processed_list[0],
                "test_interfaces.csv"
            )
            if iface_csv:
                print_success(f"Interface CSV exported: {iface_csv}")

        # Example 4: Generate summary report
        print_separator()
        print_info("Example 4: Summary Report")
        print_separator()

        report = processor.generate_summary_report(processed_list)
        print(report)

        # Save report to file
        report_file = os.path.join(processor.output_dir, "test_report.txt")
        if safe_write_file(report_file, report):
            print_success(f"\nReport saved to: {report_file}")

        print_separator()
        print_success("All examples completed successfully!")
        print_separator()

    except FileNotFoundError as e:
        print_error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
