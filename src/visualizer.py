import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Configure matplotlib backend before importing pyplot
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server environments

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from src.utils import (
    get_logger,
    get_timestamp,
    ensure_directory
)


class MetricsVisualizer:
    """
    Visualize network metrics using matplotlib charts and graphs.

    This class generates professional-quality visualizations for network monitoring
    data, including traffic comparisons, uptime status, interface statistics,
    and comprehensive dashboards.

    Attributes:
        output_dir (str): Directory where chart images are saved
        logger (logging.Logger): Logger instance for this module
        figure_size (tuple): Default figure size (width, height) in inches
        dpi (int): Dots per inch for image resolution
        style (str): Matplotlib style name

    Example:
        >>> visualizer = MetricsVisualizer(output_dir="reports/charts")
        >>> chart_path = visualizer.plot_traffic_comparison(metrics_list, top_n=10)
        >>> print(f"Chart saved to: {chart_path}")
    """

    def __init__(
        self,
        output_dir: str = "reports",
        figure_size: Tuple[int, int] = (12, 6),
        dpi: int = 100
    ) -> None:
        """
        Initialize MetricsVisualizer.

        Args:
            output_dir: Directory for saving chart images (default: "reports")
            figure_size: Default figure size as (width, height) in inches
            dpi: Resolution for saved images (default: 100)

        Example:
            visualizer = MetricsVisualizer()
            visualizer = MetricsVisualizer(output_dir="charts", figure_size=(14, 8), dpi=150)
        """
        self.output_dir = output_dir
        self.figure_size = figure_size
        self.dpi = dpi
        self.logger = get_logger(__name__)

        # Create output directory if it doesn't exist
        if not ensure_directory(self.output_dir):
            self.logger.warning(f"Failed to create output directory: {self.output_dir}")

        # Try to set matplotlib style
        try:
            plt.style.use('seaborn-v0_8-darkgrid')
            self.style = 'seaborn-v0_8-darkgrid'
            self.logger.debug("Using matplotlib style: seaborn-v0_8-darkgrid")
        except Exception:
            try:
                plt.style.use('seaborn-darkgrid')
                self.style = 'seaborn-darkgrid'
                self.logger.debug("Using matplotlib style: seaborn-darkgrid")
            except Exception:
                plt.style.use('default')
                self.style = 'default'
                self.logger.debug("Using matplotlib style: default")

        self.logger.info(
            f"MetricsVisualizer initialized - Output: {self.output_dir}, "
            f"Size: {self.figure_size}, DPI: {self.dpi}, Style: {self.style}"
        )

    def plot_traffic_comparison(
        self,
        metrics_list: List[Dict[str, Any]],
        filename: Optional[str] = None,
        top_n: int = 10
    ) -> str:
        """
        Create bar chart comparing traffic across devices.

        Generates a grouped bar chart showing incoming and outgoing traffic
        for the top N devices by total traffic volume.

        Args:
            metrics_list: List of processed metrics dictionaries
            filename: Output filename (auto-generated if None)
            top_n: Number of top devices to display (default: 10)

        Returns:
            Full filepath to saved chart image

        Example:
            >>> chart = visualizer.plot_traffic_comparison(processed_metrics, top_n=10)
            >>> print(f"Chart saved: {chart}")
        """
        self.logger.info(f"Generating traffic comparison chart (top {top_n})")

        try:
            # Filter successful metrics and extract traffic data
            valid_metrics = [m for m in metrics_list if m.get('success', False)]

            if not valid_metrics:
                self.logger.warning("No valid metrics for traffic comparison")
                return ""

            # Prepare data: device names, in traffic, out traffic
            devices_data = []
            for metrics in valid_metrics:
                summary = metrics.get('summary', {})
                total_traffic = summary.get('total_in_traffic', 0) + summary.get('total_out_traffic', 0)

                if total_traffic > 0:  # Only include devices with traffic
                    devices_data.append({
                        'name': metrics.get('device_name', 'unknown'),
                        'in_traffic': summary.get('total_in_traffic', 0),
                        'out_traffic': summary.get('total_out_traffic', 0),
                        'total': total_traffic
                    })

            if not devices_data:
                self.logger.warning("No devices with traffic data")
                return ""

            # Sort by total traffic and take top N
            devices_data.sort(key=lambda x: x['total'], reverse=True)
            devices_data = devices_data[:top_n]

            # Extract data for plotting
            device_names = [d['name'] for d in devices_data]
            in_traffic = [self._format_traffic_for_chart(d['in_traffic'])[0] for d in devices_data]
            out_traffic = [self._format_traffic_for_chart(d['out_traffic'])[0] for d in devices_data]
            unit = self._format_traffic_for_chart(devices_data[0]['total'])[1]

            # Create figure
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)

            # Bar positions
            x = range(len(device_names))
            width = 0.35

            # Create bars
            bars1 = ax.bar([i - width/2 for i in x], in_traffic, width,
                          label='Incoming', color='#3498db', alpha=0.8)
            bars2 = ax.bar([i + width/2 for i in x], out_traffic, width,
                          label='Outgoing', color='#e67e22', alpha=0.8)

            # Customize chart
            ax.set_xlabel('Device Name', fontsize=11, fontweight='bold')
            ax.set_ylabel(f'Traffic ({unit})', fontsize=11, fontweight='bold')
            ax.set_title(f'Network Traffic Comparison - Top {len(device_names)} Devices',
                        fontsize=14, fontweight='bold', pad=20)
            ax.set_xticks(x)
            ax.set_xticklabels(device_names, rotation=45, ha='right')
            ax.legend(loc='upper right', framealpha=0.9)
            ax.grid(True, alpha=0.3, linestyle='--')

            # Add value labels on bars
            self._add_value_labels(ax, bars1)
            self._add_value_labels(ax, bars2)

            # Adjust layout
            plt.tight_layout()

            # Save figure
            if filename is None:
                filename = self._generate_filename('traffic_comparison')

            filepath = self._save_figure(fig, filename)
            self.logger.info(f"Traffic comparison chart saved: {filepath}")

            return filepath

        except Exception as e:
            self.logger.error(f"Error generating traffic comparison chart: {e}")
            return ""

    def plot_device_uptime(
        self,
        metrics_list: List[Dict[str, Any]],
        filename: Optional[str] = None
    ) -> str:
        """
        Create horizontal bar chart showing device uptimes.

        Generates a color-coded horizontal bar chart with uptimes in days.
        Colors indicate uptime health: green (>30d), yellow (7-30d),
        orange (1-7d), red (<1d).

        Args:
            metrics_list: List of processed metrics dictionaries
            filename: Output filename (auto-generated if None)

        Returns:
            Full filepath to saved chart image

        Example:
            >>> chart = visualizer.plot_device_uptime(processed_metrics)
            >>> print(f"Uptime chart: {chart}")
        """
        self.logger.info("Generating device uptime chart")

        try:
            # Filter successful metrics and extract uptime data
            valid_metrics = [m for m in metrics_list if m.get('success', False)]

            if not valid_metrics:
                self.logger.warning("No valid metrics for uptime chart")
                return ""

            # Prepare data
            uptime_data = []
            for metrics in valid_metrics:
                summary = metrics.get('summary', {})
                uptime_seconds = summary.get('uptime_seconds', 0)
                uptime_days = uptime_seconds / 86400  # Convert to days

                uptime_data.append({
                    'name': metrics.get('device_name', 'unknown'),
                    'uptime_days': uptime_days,
                    'uptime_seconds': uptime_seconds
                })

            # Sort by uptime (longest first)
            uptime_data.sort(key=lambda x: x['uptime_days'], reverse=True)

            # Extract data for plotting
            device_names = [d['name'] for d in uptime_data]
            uptime_days = [d['uptime_days'] for d in uptime_data]
            colors = [self._get_uptime_color(d) for d in uptime_days]

            # Create figure
            fig, ax = plt.subplots(figsize=(self.figure_size[0], max(6, len(device_names) * 0.4)),
                                  dpi=self.dpi)

            # Create horizontal bars
            bars = ax.barh(device_names, uptime_days, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

            # Customize chart
            ax.set_xlabel('Uptime (days)', fontsize=11, fontweight='bold')
            ax.set_ylabel('Device Name', fontsize=11, fontweight='bold')
            ax.set_title('Device Uptime Status', fontsize=14, fontweight='bold', pad=20)
            ax.grid(True, alpha=0.3, linestyle='--', axis='x')

            # Add uptime values on bars
            for i, (bar, uptime) in enumerate(zip(bars, uptime_days)):
                width = bar.get_width()
                label_x_pos = width + (max(uptime_days) * 0.01)
                ax.text(label_x_pos, bar.get_y() + bar.get_height()/2,
                       f'{uptime:.1f}d', va='center', fontsize=9, fontweight='bold')

            # Add legend for color coding
            legend_elements = [
                mpatches.Patch(color='#27ae60', label='> 30 days (Excellent)'),
                mpatches.Patch(color='#f39c12', label='7-30 days (Good)'),
                mpatches.Patch(color='#e67e22', label='1-7 days (Fair)'),
                mpatches.Patch(color='#e74c3c', label='< 1 day (Poor)')
            ]
            ax.legend(handles=legend_elements, loc='lower right', framealpha=0.9)

            # Adjust layout
            plt.tight_layout()

            # Save figure
            if filename is None:
                filename = self._generate_filename('device_uptime')

            filepath = self._save_figure(fig, filename)
            self.logger.info(f"Device uptime chart saved: {filepath}")

            return filepath

        except Exception as e:
            self.logger.error(f"Error generating uptime chart: {e}")
            return ""

    def plot_interface_status(
        self,
        device_metrics: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """
        Create pie chart showing interface status distribution.

        Generates a pie chart with slices for Up, Down, and Other interface
        statuses, showing both percentages and counts.

        Args:
            device_metrics: Single device processed metrics dictionary
            filename: Output filename (auto-generated if None)

        Returns:
            Full filepath to saved chart image

        Example:
            >>> chart = visualizer.plot_interface_status(device_metrics)
            >>> print(f"Status chart: {chart}")
        """
        self.logger.info("Generating interface status pie chart")

        try:
            device_name = device_metrics.get('device_name', 'unknown')

            if not device_metrics.get('success', False):
                self.logger.warning(f"Cannot create status chart - device {device_name} collection failed")
                return ""

            # Extract interface data
            interfaces = device_metrics.get('interfaces', [])

            if not interfaces:
                self.logger.warning(f"No interfaces found for device {device_name}")
                return ""

            # Count interface statuses
            status_counts = {'up': 0, 'down': 0, 'other': 0}

            for iface in interfaces:
                status = iface.get('oper_status', 'unknown').lower()
                if status == 'up':
                    status_counts['up'] += 1
                elif status == 'down':
                    status_counts['down'] += 1
                else:
                    status_counts['other'] += 1

            # Prepare pie chart data
            labels = []
            sizes = []
            colors = []
            explode = []

            if status_counts['up'] > 0:
                labels.append(f"Up ({status_counts['up']})")
                sizes.append(status_counts['up'])
                colors.append('#27ae60')
                explode.append(0.05)

            if status_counts['down'] > 0:
                labels.append(f"Down ({status_counts['down']})")
                sizes.append(status_counts['down'])
                colors.append('#e74c3c')
                explode.append(0.05)

            if status_counts['other'] > 0:
                labels.append(f"Other ({status_counts['other']})")
                sizes.append(status_counts['other'])
                colors.append('#95a5a6')
                explode.append(0)

            if not sizes:
                self.logger.warning(f"No interface status data for device {device_name}")
                return ""

            # Create figure
            fig, ax = plt.subplots(figsize=(10, 7), dpi=self.dpi)

            # Create pie chart
            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                explode=explode,
                shadow=True,
                textprops={'fontsize': 11, 'fontweight': 'bold'}
            )

            # Enhance autotext
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontsize(12)
                autotext.set_fontweight('bold')

            # Set title
            ax.set_title(f'Interface Status Distribution - {device_name}',
                        fontsize=14, fontweight='bold', pad=20)

            # Equal aspect ratio ensures circular pie
            ax.axis('equal')

            # Adjust layout
            plt.tight_layout()

            # Save figure
            if filename is None:
                filename = self._generate_filename(f'interface_status_{device_name}')

            filepath = self._save_figure(fig, filename)
            self.logger.info(f"Interface status chart saved: {filepath}")

            return filepath

        except Exception as e:
            self.logger.error(f"Error generating interface status chart: {e}")
            return ""

    def plot_interface_errors(
        self,
        device_metrics: Dict[str, Any],
        filename: Optional[str] = None,
        top_n: int = 10
    ) -> str:
        """
        Create bar chart showing interfaces with most errors.

        Generates a grouped bar chart displaying input and output errors
        for the top N interfaces with highest error counts.

        Args:
            device_metrics: Single device processed metrics dictionary
            filename: Output filename (auto-generated if None)
            top_n: Number of top interfaces to display (default: 10)

        Returns:
            Full filepath to saved chart image

        Example:
            >>> chart = visualizer.plot_interface_errors(device_metrics, top_n=10)
            >>> print(f"Error chart: {chart}")
        """
        self.logger.info("Generating interface errors chart")

        try:
            device_name = device_metrics.get('device_name', 'unknown')

            if not device_metrics.get('success', False):
                self.logger.warning(f"Cannot create error chart - device {device_name} collection failed")
                return ""

            # Extract interface data
            interfaces = device_metrics.get('interfaces', [])

            if not interfaces:
                self.logger.warning(f"No interfaces found for device {device_name}")
                return ""

            # Filter interfaces with errors
            error_data = []
            for iface in interfaces:
                in_errors = iface.get('in_errors', 0)
                out_errors = iface.get('out_errors', 0)
                total_errors = in_errors + out_errors

                if total_errors > 0:
                    error_data.append({
                        'name': iface.get('name', 'unknown'),
                        'in_errors': in_errors,
                        'out_errors': out_errors,
                        'total_errors': total_errors
                    })

            if not error_data:
                self.logger.info(f"No errors found on device {device_name}")
                # Create a simple message chart
                fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)
                ax.text(0.5, 0.5, f'No Interface Errors Detected\n{device_name}',
                       ha='center', va='center', fontsize=16, fontweight='bold',
                       bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
                ax.axis('off')

                if filename is None:
                    filename = self._generate_filename(f'interface_errors_{device_name}')

                filepath = self._save_figure(fig, filename)
                return filepath

            # Sort by total errors and take top N
            error_data.sort(key=lambda x: x['total_errors'], reverse=True)
            error_data = error_data[:top_n]

            # Extract data for plotting
            iface_names = [d['name'] for d in error_data]
            in_errors = [d['in_errors'] for d in error_data]
            out_errors = [d['out_errors'] for d in error_data]

            # Create figure
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)

            # Bar positions
            x = range(len(iface_names))
            width = 0.35

            # Create bars
            bars1 = ax.bar([i - width/2 for i in x], in_errors, width,
                          label='In Errors', color='#e74c3c', alpha=0.8)
            bars2 = ax.bar([i + width/2 for i in x], out_errors, width,
                          label='Out Errors', color='#e67e22', alpha=0.8)

            # Customize chart
            ax.set_xlabel('Interface Name', fontsize=11, fontweight='bold')
            ax.set_ylabel('Error Count', fontsize=11, fontweight='bold')
            ax.set_title(f'Top {len(iface_names)} Interfaces by Errors - {device_name}',
                        fontsize=14, fontweight='bold', pad=20)
            ax.set_xticks(x)
            ax.set_xticklabels(iface_names, rotation=45, ha='right')
            ax.legend(loc='upper right', framealpha=0.9)
            ax.grid(True, alpha=0.3, linestyle='--', axis='y')

            # Add value labels on bars
            self._add_value_labels(ax, bars1)
            self._add_value_labels(ax, bars2)

            # Adjust layout
            plt.tight_layout()

            # Save figure
            if filename is None:
                filename = self._generate_filename(f'interface_errors_{device_name}')

            filepath = self._save_figure(fig, filename)
            self.logger.info(f"Interface errors chart saved: {filepath}")

            return filepath

        except Exception as e:
            self.logger.error(f"Error generating interface errors chart: {e}")
            return ""

    def plot_traffic_trend(
        self,
        device_metrics: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """
        Create line chart showing traffic per interface.

        Generates a line chart displaying incoming and outgoing traffic
        distribution across device interfaces.

        Args:
            device_metrics: Single device processed metrics dictionary
            filename: Output filename (auto-generated if None)

        Returns:
            Full filepath to saved chart image

        Example:
            >>> chart = visualizer.plot_traffic_trend(device_metrics)
            >>> print(f"Trend chart: {chart}")
        """
        self.logger.info("Generating traffic trend chart")

        try:
            device_name = device_metrics.get('device_name', 'unknown')

            if not device_metrics.get('success', False):
                self.logger.warning(f"Cannot create trend chart - device {device_name} collection failed")
                return ""

            # Extract interface data
            interfaces = device_metrics.get('interfaces', [])

            if not interfaces:
                self.logger.warning(f"No interfaces found for device {device_name}")
                return ""

            # Filter interfaces with traffic
            traffic_data = []
            for iface in interfaces:
                in_traffic = iface.get('in_octets', 0)
                out_traffic = iface.get('out_octets', 0)

                if in_traffic > 0 or out_traffic > 0:
                    traffic_data.append({
                        'name': iface.get('name', 'unknown'),
                        'in_traffic': in_traffic,
                        'out_traffic': out_traffic
                    })

            if not traffic_data:
                self.logger.warning(f"No traffic data for device {device_name}")
                return ""

            # Sort by total traffic
            traffic_data.sort(key=lambda x: x['in_traffic'] + x['out_traffic'], reverse=True)

            # Limit to top 15 interfaces for readability
            traffic_data = traffic_data[:15]

            # Extract data for plotting
            iface_names = [d['name'] for d in traffic_data]
            in_traffic = [self._format_traffic_for_chart(d['in_traffic'])[0] for d in traffic_data]
            out_traffic = [self._format_traffic_for_chart(d['out_traffic'])[0] for d in traffic_data]
            unit = self._format_traffic_for_chart(traffic_data[0]['in_traffic'] + traffic_data[0]['out_traffic'])[1]

            # Create figure
            fig, ax = plt.subplots(figsize=self.figure_size, dpi=self.dpi)

            # X positions
            x = range(len(iface_names))

            # Create line plots
            ax.plot(x, in_traffic, marker='o', linewidth=2, markersize=8,
                   label='In Traffic', color='#3498db', alpha=0.8)
            ax.plot(x, out_traffic, marker='s', linewidth=2, markersize=8,
                   label='Out Traffic', color='#e67e22', alpha=0.8)

            # Customize chart
            ax.set_xlabel('Interface Name', fontsize=11, fontweight='bold')
            ax.set_ylabel(f'Traffic ({unit})', fontsize=11, fontweight='bold')
            ax.set_title(f'Interface Traffic Distribution - {device_name}',
                        fontsize=14, fontweight='bold', pad=20)
            ax.set_xticks(x)
            ax.set_xticklabels(iface_names, rotation=45, ha='right')
            ax.legend(loc='upper right', framealpha=0.9)
            ax.grid(True, alpha=0.3, linestyle='--')

            # Adjust layout
            plt.tight_layout()

            # Save figure
            if filename is None:
                filename = self._generate_filename(f'traffic_trend_{device_name}')

            filepath = self._save_figure(fig, filename)
            self.logger.info(f"Traffic trend chart saved: {filepath}")

            return filepath

        except Exception as e:
            self.logger.error(f"Error generating traffic trend chart: {e}")
            return ""

    def plot_top_talkers(
        self,
        metrics_list: List[Dict[str, Any]],
        filename: Optional[str] = None,
        top_n: int = 5
    ) -> str:
        """
        Create bar chart showing devices with highest traffic.

        Generates a horizontal bar chart displaying total traffic (in + out)
        for the top N devices sorted by traffic volume.

        Args:
            metrics_list: List of processed metrics dictionaries
            filename: Output filename (auto-generated if None)
            top_n: Number of top devices to display (default: 5)

        Returns:
            Full filepath to saved chart image

        Example:
            >>> chart = visualizer.plot_top_talkers(processed_metrics, top_n=5)
            >>> print(f"Top talkers: {chart}")
        """
        self.logger.info(f"Generating top talkers chart (top {top_n})")

        try:
            # Filter successful metrics
            valid_metrics = [m for m in metrics_list if m.get('success', False)]

            if not valid_metrics:
                self.logger.warning("No valid metrics for top talkers")
                return ""

            # Calculate total traffic per device
            device_traffic = []
            for metrics in valid_metrics:
                summary = metrics.get('summary', {})
                total = summary.get('total_in_traffic', 0) + summary.get('total_out_traffic', 0)

                if total > 0:
                    device_traffic.append({
                        'name': metrics.get('device_name', 'unknown'),
                        'ip': metrics.get('ip', 'unknown'),
                        'total': total
                    })

            if not device_traffic:
                self.logger.warning("No devices with traffic data")
                return ""

            # Sort and take top N
            device_traffic.sort(key=lambda x: x['total'], reverse=True)
            device_traffic = device_traffic[:top_n]

            # Extract data for plotting
            device_labels = [f"{d['name']}\n({d['ip']})" for d in device_traffic]
            traffic_values = [self._format_traffic_for_chart(d['total'])[0] for d in device_traffic]
            traffic_labels = [self._format_traffic_for_chart(d['total']) for d in device_traffic]
            unit = traffic_labels[0][1]

            # Create figure
            fig, ax = plt.subplots(figsize=(10, max(6, len(device_labels) * 0.5)), dpi=self.dpi)

            # Create horizontal bars with gradient colors
            colors = plt.cm.RdYlGn_r(range(len(traffic_values)))
            bars = ax.barh(device_labels, traffic_values, color=colors, alpha=0.8,
                          edgecolor='black', linewidth=0.5)

            # Customize chart
            ax.set_xlabel(f'Total Traffic ({unit})', fontsize=11, fontweight='bold')
            ax.set_ylabel('Device', fontsize=11, fontweight='bold')
            ax.set_title(f'Top {len(device_labels)} Devices by Total Traffic',
                        fontsize=14, fontweight='bold', pad=20)
            ax.grid(True, alpha=0.3, linestyle='--', axis='x')

            # Add value labels
            for i, (bar, label) in enumerate(zip(bars, traffic_labels)):
                width = bar.get_width()
                label_x_pos = width + (max(traffic_values) * 0.01)
                ax.text(label_x_pos, bar.get_y() + bar.get_height()/2,
                       f'{label[0]:.1f} {label[1]}',
                       va='center', fontsize=10, fontweight='bold')

            # Adjust layout
            plt.tight_layout()

            # Save figure
            if filename is None:
                filename = self._generate_filename('top_talkers')

            filepath = self._save_figure(fig, filename)
            self.logger.info(f"Top talkers chart saved: {filepath}")

            return filepath

        except Exception as e:
            self.logger.error(f"Error generating top talkers chart: {e}")
            return ""

    def plot_network_summary(
        self,
        aggregated_metrics: Dict[str, Any],
        filename: Optional[str] = None
    ) -> str:
        """
        Create multi-panel summary dashboard.

        Generates a comprehensive dashboard with four panels showing:
        1. Total traffic by device (bar chart)
        2. Interface status across network (pie chart)
        3. Devices by uptime (horizontal bar)
        4. Summary statistics (text)

        Args:
            aggregated_metrics: Aggregated metrics from MetricsProcessor.aggregate_metrics()
            filename: Output filename (auto-generated if None)

        Returns:
            Full filepath to saved chart image

        Example:
            >>> aggregated = processor.aggregate_metrics(metrics_list)
            >>> dashboard = visualizer.plot_network_summary(aggregated)
            >>> print(f"Dashboard: {dashboard}")
        """
        self.logger.info("Generating network summary dashboard")

        try:
            # Create figure with 2x2 subplots
            fig = plt.figure(figsize=(16, 12), dpi=self.dpi)
            gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)

            # Panel 1: Top devices by traffic (bar chart)
            ax1 = fig.add_subplot(gs[0, 0])
            self._create_traffic_summary_panel(ax1, aggregated_metrics)

            # Panel 2: Interface status (pie chart)
            ax2 = fig.add_subplot(gs[0, 1])
            self._create_interface_status_panel(ax2, aggregated_metrics)

            # Panel 3: Device uptime (horizontal bar)
            ax3 = fig.add_subplot(gs[1, 0])
            self._create_uptime_summary_panel(ax3, aggregated_metrics)

            # Panel 4: Summary statistics (text)
            ax4 = fig.add_subplot(gs[1, 1])
            self._create_statistics_panel(ax4, aggregated_metrics)

            # Overall title
            fig.suptitle('Network Summary Dashboard',
                        fontsize=18, fontweight='bold', y=0.98)

            # Save figure
            if filename is None:
                filename = self._generate_filename('network_summary_dashboard')

            filepath = self._save_figure(fig, filename)
            self.logger.info(f"Network summary dashboard saved: {filepath}")

            return filepath

        except Exception as e:
            self.logger.error(f"Error generating network summary dashboard: {e}")
            return ""

    def create_report_dashboard(
        self,
        metrics_list: List[Dict[str, Any]],
        filename: Optional[str] = None
    ) -> str:
        """
        Create comprehensive dashboard with multiple charts.

        Combines traffic comparison, uptime, and status charts into a single
        multi-panel figure for comprehensive network reporting.

        Args:
            metrics_list: List of processed metrics dictionaries
            filename: Output filename (auto-generated if None)

        Returns:
            Full filepath to saved chart image

        Example:
            >>> dashboard = visualizer.create_report_dashboard(processed_metrics)
            >>> print(f"Report dashboard: {dashboard}")
        """
        self.logger.info("Generating comprehensive report dashboard")

        try:
            # Create figure with 2x2 subplots
            fig = plt.figure(figsize=(18, 14), dpi=self.dpi)
            gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)

            # Panel 1: Traffic comparison
            ax1 = fig.add_subplot(gs[0, :])  # Top row, full width
            self._create_traffic_comparison_panel(ax1, metrics_list, top_n=8)

            # Panel 2: Interface status summary
            ax2 = fig.add_subplot(gs[1, 0])
            self._create_aggregated_interface_status_panel(ax2, metrics_list)

            # Panel 3: Device uptime
            ax3 = fig.add_subplot(gs[1, 1])
            self._create_uptime_comparison_panel(ax3, metrics_list, top_n=8)

            # Overall title
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            fig.suptitle(f'Network Monitoring Report Dashboard\nGenerated: {timestamp}',
                        fontsize=18, fontweight='bold', y=0.98)

            # Save figure
            if filename is None:
                filename = self._generate_filename('report_dashboard')

            filepath = self._save_figure(fig, filename)
            self.logger.info(f"Report dashboard saved: {filepath}")

            return filepath

        except Exception as e:
            self.logger.error(f"Error generating report dashboard: {e}")
            return ""

    # ========================================================================
    # HELPER METHODS - Chart Creation
    # ========================================================================

    def _create_traffic_summary_panel(self, ax, aggregated_metrics: Dict[str, Any]) -> None:
        """Create traffic summary panel for dashboard."""
        devices_summary = aggregated_metrics.get('top_devices_by_traffic', [])[:5]

        if not devices_summary:
            ax.text(0.5, 0.5, 'No Traffic Data', ha='center', va='center', fontsize=14)
            ax.axis('off')
            return

        device_names = [d['device_name'] for d in devices_summary]
        traffic_values = [self._format_traffic_for_chart(d['total_traffic'])[0] for d in devices_summary]
        unit = self._format_traffic_for_chart(devices_summary[0]['total_traffic'])[1]

        bars = ax.barh(device_names, traffic_values, color='#3498db', alpha=0.7)

        ax.set_xlabel(f'Total Traffic ({unit})', fontweight='bold')
        ax.set_title('Top 5 Devices by Traffic', fontweight='bold', pad=10)
        ax.grid(True, alpha=0.3, axis='x')

    def _create_interface_status_panel(self, ax, aggregated_metrics: Dict[str, Any]) -> None:
        """Create interface status panel for dashboard."""
        total_active = aggregated_metrics.get('total_active_interfaces', 0)
        total_interfaces = aggregated_metrics.get('total_interfaces', 0)
        total_inactive = total_interfaces - total_active

        if total_interfaces == 0:
            ax.text(0.5, 0.5, 'No Interface Data', ha='center', va='center', fontsize=14)
            ax.axis('off')
            return

        sizes = []
        labels = []
        colors = []

        if total_active > 0:
            sizes.append(total_active)
            labels.append(f'Active ({total_active})')
            colors.append('#27ae60')

        if total_inactive > 0:
            sizes.append(total_inactive)
            labels.append(f'Inactive ({total_inactive})')
            colors.append('#e74c3c')

        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
              startangle=90, textprops={'fontweight': 'bold'})
        ax.set_title('Network-Wide Interface Status', fontweight='bold', pad=10)

    def _create_uptime_summary_panel(self, ax, aggregated_metrics: Dict[str, Any]) -> None:
        """Create uptime summary panel for dashboard."""
        devices_summary = aggregated_metrics.get('devices_summary', [])

        # Filter and sort by uptime
        valid_devices = [d for d in devices_summary if d.get('uptime_seconds', 0) > 0]
        valid_devices.sort(key=lambda x: x.get('uptime_seconds', 0), reverse=True)
        valid_devices = valid_devices[:5]

        if not valid_devices:
            ax.text(0.5, 0.5, 'No Uptime Data', ha='center', va='center', fontsize=14)
            ax.axis('off')
            return

        device_names = [d['device_name'] for d in valid_devices]
        uptime_days = [d['uptime_seconds'] / 86400 for d in valid_devices]
        colors = [self._get_uptime_color(d) for d in uptime_days]

        bars = ax.barh(device_names, uptime_days, color=colors, alpha=0.7)

        ax.set_xlabel('Uptime (days)', fontweight='bold')
        ax.set_title('Top 5 Devices by Uptime', fontweight='bold', pad=10)
        ax.grid(True, alpha=0.3, axis='x')

    def _create_statistics_panel(self, ax, aggregated_metrics: Dict[str, Any]) -> None:
        """Create statistics text panel for dashboard."""
        ax.axis('off')

        stats_text = f"""
        NETWORK STATISTICS
        {'='*40}

        Total Devices:         {aggregated_metrics.get('total_devices', 0)}
        Successful:            {aggregated_metrics.get('successful_collections', 0)}
        Failed:                {aggregated_metrics.get('failed_collections', 0)}

        Total Interfaces:      {aggregated_metrics.get('total_interfaces', 0)}
        Active Interfaces:     {aggregated_metrics.get('total_active_interfaces', 0)}

        Total Inbound:         {aggregated_metrics.get('total_traffic_in_readable', '0 B')}
        Total Outbound:        {aggregated_metrics.get('total_traffic_out_readable', '0 B')}

        Average Uptime:        {aggregated_metrics.get('average_uptime_readable', 'N/A')}

        Devices with Errors:   {len(aggregated_metrics.get('devices_with_errors', []))}
        """

        ax.text(0.1, 0.95, stats_text, transform=ax.transAxes,
               fontsize=11, verticalalignment='top', fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

    def _create_traffic_comparison_panel(self, ax, metrics_list: List[Dict[str, Any]], top_n: int = 8) -> None:
        """Create traffic comparison panel for dashboard."""
        valid_metrics = [m for m in metrics_list if m.get('success', False)]

        devices_data = []
        for metrics in valid_metrics:
            summary = metrics.get('summary', {})
            total = summary.get('total_in_traffic', 0) + summary.get('total_out_traffic', 0)
            if total > 0:
                devices_data.append({
                    'name': metrics.get('device_name', 'unknown'),
                    'in': summary.get('total_in_traffic', 0),
                    'out': summary.get('total_out_traffic', 0),
                    'total': total
                })

        devices_data.sort(key=lambda x: x['total'], reverse=True)
        devices_data = devices_data[:top_n]

        if not devices_data:
            ax.text(0.5, 0.5, 'No Traffic Data', ha='center', va='center', fontsize=14)
            ax.axis('off')
            return

        names = [d['name'] for d in devices_data]
        in_traffic = [self._format_traffic_for_chart(d['in'])[0] for d in devices_data]
        out_traffic = [self._format_traffic_for_chart(d['out'])[0] for d in devices_data]
        unit = self._format_traffic_for_chart(devices_data[0]['total'])[1]

        x = range(len(names))
        width = 0.35

        ax.bar([i - width/2 for i in x], in_traffic, width, label='Incoming', color='#3498db', alpha=0.8)
        ax.bar([i + width/2 for i in x], out_traffic, width, label='Outgoing', color='#e67e22', alpha=0.8)

        ax.set_ylabel(f'Traffic ({unit})', fontweight='bold')
        ax.set_title(f'Traffic Comparison - Top {len(names)} Devices', fontweight='bold', pad=10)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha='right')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

    def _create_aggregated_interface_status_panel(self, ax, metrics_list: List[Dict[str, Any]]) -> None:
        """Create aggregated interface status panel for dashboard."""
        total_up = 0
        total_down = 0
        total_other = 0

        for metrics in metrics_list:
            if metrics.get('success', False):
                for iface in metrics.get('interfaces', []):
                    status = iface.get('oper_status', 'unknown').lower()
                    if status == 'up':
                        total_up += 1
                    elif status == 'down':
                        total_down += 1
                    else:
                        total_other += 1

        sizes = []
        labels = []
        colors = []

        if total_up > 0:
            sizes.append(total_up)
            labels.append(f'Up ({total_up})')
            colors.append('#27ae60')

        if total_down > 0:
            sizes.append(total_down)
            labels.append(f'Down ({total_down})')
            colors.append('#e74c3c')

        if total_other > 0:
            sizes.append(total_other)
            labels.append(f'Other ({total_other})')
            colors.append('#95a5a6')

        if sizes:
            ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                  startangle=90, textprops={'fontweight': 'bold'})
            ax.set_title('Network-Wide Interface Status', fontweight='bold', pad=10)
        else:
            ax.text(0.5, 0.5, 'No Interface Data', ha='center', va='center', fontsize=14)
            ax.axis('off')

    def _create_uptime_comparison_panel(self, ax, metrics_list: List[Dict[str, Any]], top_n: int = 8) -> None:
        """Create uptime comparison panel for dashboard."""
        uptime_data = []
        for metrics in metrics_list:
            if metrics.get('success', False):
                summary = metrics.get('summary', {})
                uptime_seconds = summary.get('uptime_seconds', 0)
                if uptime_seconds > 0:
                    uptime_data.append({
                        'name': metrics.get('device_name', 'unknown'),
                        'uptime_days': uptime_seconds / 86400
                    })

        uptime_data.sort(key=lambda x: x['uptime_days'], reverse=True)
        uptime_data = uptime_data[:top_n]

        if not uptime_data:
            ax.text(0.5, 0.5, 'No Uptime Data', ha='center', va='center', fontsize=14)
            ax.axis('off')
            return

        names = [d['name'] for d in uptime_data]
        days = [d['uptime_days'] for d in uptime_data]
        colors = [self._get_uptime_color(d) for d in days]

        ax.barh(names, days, color=colors, alpha=0.7)
        ax.set_xlabel('Uptime (days)', fontweight='bold')
        ax.set_title(f'Device Uptime - Top {len(names)}', fontweight='bold', pad=10)
        ax.grid(True, alpha=0.3, axis='x')

    # ========================================================================
    # HELPER METHODS - Utilities
    # ========================================================================

    def _format_traffic_for_chart(self, bytes_value: int) -> Tuple[float, str]:
        """
        Convert bytes to appropriate unit for chart display.

        Args:
            bytes_value: Traffic value in bytes

        Returns:
            Tuple of (value, unit) for chart display

        Example:
            >>> visualizer._format_traffic_for_chart(1500000000)
            (1.4, 'GB')
            >>> visualizer._format_traffic_for_chart(500000)
            (488.3, 'KB')
        """
        if bytes_value < 0:
            return (0.0, 'B')

        if bytes_value == 0:
            return (0.0, 'B')

        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        unit_index = 0
        value = float(bytes_value)

        while value >= 1024.0 and unit_index < len(units) - 1:
            value /= 1024.0
            unit_index += 1

        return (value, units[unit_index])

    def _get_uptime_color(self, uptime_days: float) -> str:
        """
        Return color based on uptime threshold.

        Args:
            uptime_days: Uptime in days

        Returns:
            Color string for matplotlib

        Color scheme:
            - Green: > 30 days (excellent)
            - Yellow: 7-30 days (good)
            - Orange: 1-7 days (fair)
            - Red: < 1 day (poor)
        """
        if uptime_days > 30:
            return '#27ae60'  # Green
        elif uptime_days > 7:
            return '#f39c12'  # Yellow
        elif uptime_days >= 1:
            return '#e67e22'  # Orange
        else:
            return '#e74c3c'  # Red

    def _generate_filename(self, chart_type: str) -> str:
        """
        Generate filename with timestamp.

        Args:
            chart_type: Type of chart (used as prefix)

        Returns:
            Filename string (not full path)

        Example:
            >>> visualizer._generate_filename('traffic_comparison')
            'traffic_comparison_20250204_143022.png'
        """
        timestamp = get_timestamp()
        return f"{chart_type}_{timestamp}.png"

    def _save_figure(self, fig, filename: str) -> str:
        """
        Save matplotlib figure to file.

        Args:
            fig: Matplotlib figure object
            filename: Output filename (just name, not path)

        Returns:
            Full filepath to saved image

        Saves with tight bounding box and closes figure to free memory.
        """
        try:
            # Ensure filename ends with .png
            if not filename.endswith('.png'):
                filename += '.png'

            filepath = os.path.join(self.output_dir, filename)

            # Save with tight layout
            fig.savefig(filepath, dpi=self.dpi, bbox_inches='tight', facecolor='white')

            # Close figure to free memory
            plt.close(fig)

            self.logger.debug(f"Figure saved: {filepath}")
            return filepath

        except Exception as e:
            self.logger.error(f"Error saving figure {filename}: {e}")
            plt.close(fig)
            return ""

    def _add_value_labels(self, ax, bars) -> None:
        """
        Add value labels on top of bars.

        Args:
            ax: Matplotlib axis object
            bars: Bar container from ax.bar() or ax.barh()
        """
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}',
                       ha='center', va='bottom', fontsize=8, fontweight='bold')

    def _apply_chart_styling(self, ax) -> None:
        """
        Apply consistent styling to chart axes.

        Args:
            ax: Matplotlib axis object

        Applies grid, removes spines, sets label formatting, etc.
        """
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)


# ============================================================================
# MODULE TESTING AND EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    """
    Example usage and testing of MetricsVisualizer class.
    Run this script directly to test visualization functionality.
    """
    from src.utils import setup_logging, print_success, print_error, print_info, print_separator
    from src.snmp_monitor import SNMPMonitor
    from src.metrics_processor import MetricsProcessor

    # Setup logging
    logger = setup_logging(log_level="INFO")

    print_separator()
    print("Metrics Visualizer - Example Usage")
    print_separator()

    try:
        # Initialize components
        print_info("Initializing components...")
        visualizer = MetricsVisualizer(output_dir="reports/charts", figure_size=(12, 6), dpi=100)
        monitor = SNMPMonitor(
            inventory_path="inventory/devices.yaml",
            default_community="public",
            timeout=5,
            retries=2
        )
        processor = MetricsProcessor(output_dir="reports")

        # Get SNMP-enabled devices
        devices = monitor.inventory_loader.get_snmp_enabled_devices()
        print_info(f"Found {len(devices)} SNMP-enabled devices")

        if not devices:
            print_error("No SNMP-enabled devices found")
            sys.exit(1)

        # Collect and process metrics
        print_separator()
        print_info("Collecting and processing metrics...")
        print_separator()

        raw_list = monitor.collect_multiple_devices(devices[:5], parallel=True)
        processed_list = [processor.process_device_metrics(m) for m in raw_list]

        print_success(f"Processed {len(processed_list)} devices")

        # Example 1: Traffic comparison
        print_separator()
        print_info("Example 1: Traffic Comparison Chart")
        print_separator()

        traffic_chart = visualizer.plot_traffic_comparison(processed_list, top_n=10)
        if traffic_chart:
            print_success(f"Traffic chart saved: {traffic_chart}")

        # Example 2: Device uptime
        print_separator()
        print_info("Example 2: Device Uptime Chart")
        print_separator()

        uptime_chart = visualizer.plot_device_uptime(processed_list)
        if uptime_chart:
            print_success(f"Uptime chart saved: {uptime_chart}")

        # Example 3: Interface status for first device
        print_separator()
        print_info("Example 3: Interface Status Pie Chart")
        print_separator()

        if processed_list and processed_list[0].get('success', False):
            status_chart = visualizer.plot_interface_status(processed_list[0])
            if status_chart:
                print_success(f"Status chart saved: {status_chart}")

        # Example 4: Interface errors
        print_separator()
        print_info("Example 4: Interface Errors Chart")
        print_separator()

        if processed_list and processed_list[0].get('success', False):
            errors_chart = visualizer.plot_interface_errors(processed_list[0], top_n=10)
            if errors_chart:
                print_success(f"Errors chart saved: {errors_chart}")

        # Example 5: Traffic trend
        print_separator()
        print_info("Example 5: Traffic Trend Chart")
        print_separator()

        if processed_list and processed_list[0].get('success', False):
            trend_chart = visualizer.plot_traffic_trend(processed_list[0])
            if trend_chart:
                print_success(f"Trend chart saved: {trend_chart}")

        # Example 6: Top talkers
        print_separator()
        print_info("Example 6: Top Talkers Chart")
        print_separator()

        talkers_chart = visualizer.plot_top_talkers(processed_list, top_n=5)
        if talkers_chart:
            print_success(f"Top talkers chart saved: {talkers_chart}")

        # Example 7: Network summary dashboard
        print_separator()
        print_info("Example 7: Network Summary Dashboard")
        print_separator()

        aggregated = processor.aggregate_metrics(processed_list)
        summary_dashboard = visualizer.plot_network_summary(aggregated)
        if summary_dashboard:
            print_success(f"Summary dashboard saved: {summary_dashboard}")

        # Example 8: Comprehensive report dashboard
        print_separator()
        print_info("Example 8: Comprehensive Report Dashboard")
        print_separator()

        report_dashboard = visualizer.create_report_dashboard(processed_list)
        if report_dashboard:
            print_success(f"Report dashboard saved: {report_dashboard}")

        print_separator()
        print_success("All visualization examples completed!")
        print_separator()

    except FileNotFoundError as e:
        print_error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
