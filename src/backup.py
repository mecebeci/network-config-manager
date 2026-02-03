import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from connection_manager import ConnectionManager
from inventory_loader import InventoryLoader
from utils import (
    get_logger,
    get_timestamp,
    get_human_timestamp,
    safe_write_file,
    safe_read_file,
    list_files,
    ensure_directory,
    create_progress_bar,
    format_device_list,
)
from exceptions import (
    ConnectionError,
    AuthenticationError,
    TimeoutError,
    CommandExecutionError,
    DeviceNotReachableError,
)


class ConfigBackup:
    """
    Automated configuration backup manager for network devices.

    This class handles retrieving device configurations via SSH and storing them
    with timestamps. It supports single and multi-device operations with both
    parallel and sequential execution modes.

    Attributes:
        inventory_loader (InventoryLoader): Inventory management instance
        backup_dir (str): Directory for storing backup files
        logger (logging.Logger): Logger instance for this module
        retention_days (int): Number of days to retain backups
    """

    def __init__(
        self,
        inventory_path: str = "inventory/devices.yaml",
        backup_dir: str = "configs/backups",
        retention_days: int = 30
    ):
        """
        Initialize ConfigBackup manager.

        Args:
            inventory_path: Path to inventory YAML file (default: inventory/devices.yaml)
            backup_dir: Directory to store backups (default: configs/backups)
            retention_days: Days to retain old backups (default: 30)

        Example:
            backup_mgr = ConfigBackup(
                inventory_path="inventory/devices.yaml",
                backup_dir="configs/backups",
                retention_days=30
            )
        """
        self.logger = get_logger(__name__)
        self.backup_dir = backup_dir
        self.retention_days = retention_days

        # Initialize inventory loader
        try:
            self.inventory_loader = InventoryLoader(inventory_path)
            self.logger.info(f"Inventory loaded from {inventory_path}")
        except Exception as e:
            self.logger.error(f"Failed to load inventory: {e}")
            raise

        # Create backup directory if needed
        if ensure_directory(backup_dir):
            self.logger.info(f"Backup directory ready: {backup_dir}")
        else:
            self.logger.error(f"Failed to create backup directory: {backup_dir}")
            raise RuntimeError(f"Cannot create backup directory: {backup_dir}")

        self.logger.info(
            f"ConfigBackup initialized - Directory: {backup_dir}, "
            f"Retention: {retention_days} days"
        )

    def _merge_device_settings(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge device-specific settings with global settings.

        Creates a complete device configuration by combining device-specific
        attributes with global settings (username, password, etc.).

        Args:
            device: Device dictionary from inventory

        Returns:
            Complete device configuration with all required fields

        Example:
            device_config = self._merge_device_settings(device)
        """
        settings = self.inventory_loader.get_settings()

        # Create merged device config
        merged = device.copy()

        # Add credentials from global settings if not in device
        if 'username' not in merged:
            merged['username'] = settings.get('default_username')

        if 'password' not in merged:
            merged['password'] = settings.get('default_password')

        if 'timeout' not in merged:
            merged['timeout'] = settings.get('connection_timeout', 10)

        return merged

    def _get_device_config(self, conn_mgr: ConnectionManager, device: Dict[str, Any]) -> str:
        """
        Retrieve configuration from device.

        Executes appropriate commands to retrieve running configuration
        based on device type.

        Args:
            conn_mgr: Active ConnectionManager instance
            device: Device dictionary

        Returns:
            Configuration text

        Raises:
            CommandExecutionError: If configuration retrieval fails
        """
        device_type = device.get('device_type', 'nokia_sros')
        device_name = device.get('name', 'unknown')

        self.logger.debug(f"Retrieving configuration for {device_name} (type: {device_type})")

        try:
            # SR Linux (Nokia SROS) configuration commands
            if device_type in ['nokia_sros', 'sr_linux']:
                # Try "info flat" command for SR Linux
                self.logger.debug(f"Using 'info flat' command for {device_name}")
                config = conn_mgr.send_command("info flat")

                # If empty or error, try alternative command
                if not config or len(config.strip()) < 50:
                    self.logger.debug(f"Trying alternative command for {device_name}")
                    config = conn_mgr.send_command("admin show configuration")

            else:
                # Generic approach for other device types
                self.logger.debug(f"Using 'show running-config' for {device_name}")
                config = conn_mgr.send_command("show running-config")

            if not config:
                raise CommandExecutionError(
                    "Retrieved configuration is empty",
                    device_name=device_name
                )

            self.logger.debug(
                f"Configuration retrieved for {device_name} "
                f"({len(config)} characters)"
            )

            return config

        except Exception as e:
            self.logger.error(f"Failed to retrieve config from {device_name}: {e}")
            raise

    def backup_device(self, device: Dict[str, Any], verify: bool = True) -> Dict[str, Any]:
        """
        Backup configuration for a single device.

        Connects to the device, retrieves configuration, and saves it
        with a timestamp. Optionally verifies the backup file.

        Args:
            device: Device dictionary with connection details
            verify: Whether to verify backup after saving (default: True)

        Returns:
            Result dictionary with keys:
                - success (bool): Whether backup succeeded
                - device_name (str): Device name
                - filepath (str or None): Path to backup file
                - timestamp (str): Timestamp of backup
                - error (str or None): Error message if failed
                - file_size (int or None): Backup file size in bytes

        Example:
            device = inventory_loader.get_device_by_name("spine1")
            result = backup_mgr.backup_device(device, verify=True)
            if result['success']:
                print(f"Backup saved to {result['filepath']}")
        """
        device_name = device.get('name', device.get('ip', 'unknown'))
        result = {
            'success': False,
            'device_name': device_name,
            'filepath': None,
            'timestamp': get_human_timestamp(),
            'error': None,
            'file_size': None
        }

        self.logger.info(f"Starting backup for device '{device_name}'")

        try:
            # Merge device settings with global settings
            device_config = self._merge_device_settings(device)

            # Validate required fields
            required_fields = ['name', 'ip', 'username', 'password']
            missing_fields = [f for f in required_fields if not device_config.get(f)]

            if missing_fields:
                error_msg = f"Missing required fields: {', '.join(missing_fields)}"
                self.logger.error(f"Device '{device_name}': {error_msg}")
                result['error'] = error_msg
                return result

            # Connect to device and retrieve configuration
            with ConnectionManager(device_config) as conn:
                self.logger.info(f"Connected to device '{device_name}', retrieving configuration")

                # Get configuration
                config = self._get_device_config(conn, device_config)

                # Generate filename with timestamp
                timestamp = get_timestamp()
                filename = f"{device_name}_{timestamp}.cfg"
                filepath = os.path.join(self.backup_dir, filename)

                # Add metadata header to configuration
                header = (
                    f"# Configuration Backup\n"
                    f"# Device: {device_name}\n"
                    f"# IP: {device_config['ip']}\n"
                    f"# Timestamp: {get_human_timestamp()}\n"
                    f"# Device Type: {device_config.get('device_type', 'unknown')}\n"
                    f"#\n"
                    f"# {'=' * 70}\n\n"
                )

                full_content = header + config

                # Save configuration to file
                if safe_write_file(filepath, full_content):
                    self.logger.info(f"Configuration saved to {filepath}")
                    result['filepath'] = filepath
                    result['file_size'] = len(full_content)

                    # Verify backup if requested
                    if verify:
                        if self.verify_backup(filepath):
                            self.logger.info(f"Backup verified for '{device_name}'")
                            result['success'] = True
                        else:
                            error_msg = "Backup verification failed"
                            self.logger.error(f"Device '{device_name}': {error_msg}")
                            result['error'] = error_msg
                    else:
                        result['success'] = True
                else:
                    error_msg = f"Failed to write backup file: {filepath}"
                    self.logger.error(error_msg)
                    result['error'] = error_msg

        except (ConnectionError, AuthenticationError, DeviceNotReachableError) as e:
            error_msg = str(e)
            self.logger.error(f"Connection failed for device '{device_name}': {error_msg}")
            result['error'] = error_msg

        except CommandExecutionError as e:
            error_msg = str(e)
            self.logger.error(f"Command execution failed for device '{device_name}': {error_msg}")
            result['error'] = error_msg

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(f"Backup failed for device '{device_name}': {error_msg}")
            result['error'] = error_msg

        return result

    def backup_multiple_devices(
        self,
        devices: List[Dict[str, Any]],
        parallel: bool = True,
        max_workers: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Backup multiple devices with parallel or sequential execution.

        Args:
            devices: List of device dictionaries
            parallel: Whether to use parallel execution (default: True)
            max_workers: Maximum number of parallel workers (default: 5)

        Returns:
            List of result dictionaries from backup_device()

        Example:
            devices = inventory_loader.get_devices_by_role("spine")
            results = backup_mgr.backup_multiple_devices(
                devices,
                parallel=True,
                max_workers=5
            )
        """
        if not devices:
            self.logger.warning("No devices provided for backup")
            return []

        device_count = len(devices)
        self.logger.info(
            f"Starting backup for {device_count} devices "
            f"(mode: {'parallel' if parallel else 'sequential'})"
        )

        results = []

        if parallel:
            # Parallel execution using ThreadPoolExecutor
            self.logger.info(f"Using {max_workers} parallel workers")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all backup tasks
                future_to_device = {
                    executor.submit(self.backup_device, device): device
                    for device in devices
                }

                # Process results as they complete with progress indicator
                for future in create_progress_bar(
                    as_completed(future_to_device),
                    description="Backing up devices",
                    total=device_count
                ):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        device = future_to_device[future]
                        device_name = device.get('name', 'unknown')
                        self.logger.error(f"Backup task failed for {device_name}: {e}")
                        results.append({
                            'success': False,
                            'device_name': device_name,
                            'filepath': None,
                            'timestamp': get_human_timestamp(),
                            'error': str(e),
                            'file_size': None
                        })

        else:
            # Sequential execution
            for device in create_progress_bar(devices, description="Backing up devices"):
                result = self.backup_device(device)
                results.append(result)

        # Log summary
        success_count = sum(1 for r in results if r['success'])
        failed_count = device_count - success_count

        self.logger.info(
            f"Backup complete - Total: {device_count}, "
            f"Success: {success_count}, Failed: {failed_count}"
        )

        return results

    def backup_all_devices(self, parallel: bool = True) -> List[Dict[str, Any]]:
        """
        Backup all devices from inventory.

        Args:
            parallel: Whether to use parallel execution (default: True)

        Returns:
            List of result dictionaries

        Example:
            results = backup_mgr.backup_all_devices(parallel=True)
            report = backup_mgr.generate_backup_report(results)
        """
        self.logger.info("Backing up all devices from inventory")
        devices = self.inventory_loader.get_all_devices()
        return self.backup_multiple_devices(devices, parallel=parallel)

    def backup_devices_by_role(self, role: str, parallel: bool = True) -> List[Dict[str, Any]]:
        """
        Backup devices filtered by role.

        Args:
            role: Device role to filter (e.g., 'spine', 'leaf', 'border')
            parallel: Whether to use parallel execution (default: True)

        Returns:
            List of result dictionaries

        Example:
            # Backup all spine switches
            results = backup_mgr.backup_devices_by_role("spine", parallel=True)
        """
        self.logger.info(f"Backing up devices with role '{role}'")
        devices = self.inventory_loader.get_devices_by_role(role)

        if not devices:
            self.logger.warning(f"No devices found with role '{role}'")
            return []

        return self.backup_multiple_devices(devices, parallel=parallel)

    def get_latest_backup(self, device_name: str) -> Optional[str]:
        """
        Find the most recent backup file for a device.

        Args:
            device_name: Name of the device

        Returns:
            Path to latest backup file, or None if not found

        Example:
            latest = backup_mgr.get_latest_backup("spine1")
            if latest:
                print(f"Latest backup: {latest}")
        """
        self.logger.debug(f"Looking for latest backup of device '{device_name}'")

        # List all backup files for this device
        backups = self.list_device_backups(device_name)

        if backups:
            # Files are already sorted by date (newest first)
            latest = backups[0]
            self.logger.debug(f"Latest backup for '{device_name}': {latest}")
            return latest
        else:
            self.logger.debug(f"No backups found for device '{device_name}'")
            return None

    def list_device_backups(self, device_name: str) -> List[str]:
        """
        List all backup files for a device.

        Args:
            device_name: Name of the device

        Returns:
            List of backup file paths sorted by date (newest first)

        Example:
            backups = backup_mgr.list_device_backups("spine1")
            for backup in backups:
                print(backup)
        """
        self.logger.debug(f"Listing backups for device '{device_name}'")

        # Get all .cfg files in backup directory
        all_backups = list_files(self.backup_dir, extension=".cfg", sort_by_date=True)

        # Filter for this specific device (filename starts with device_name_)
        device_backups = [
            f for f in all_backups
            if os.path.basename(f).startswith(f"{device_name}_")
        ]

        self.logger.debug(f"Found {len(device_backups)} backups for '{device_name}'")
        return device_backups

    def verify_backup(self, filepath: str) -> bool:
        """
        Verify that a backup file is valid.

        Checks:
        - File exists
        - File is readable
        - File has content (size > 0)
        - File contains expected configuration markers

        Args:
            filepath: Path to backup file

        Returns:
            True if backup is valid, False otherwise

        Example:
            if backup_mgr.verify_backup("configs/backups/spine1_20250203_143022.cfg"):
                print("Backup is valid")
        """
        self.logger.debug(f"Verifying backup file: {filepath}")

        # Check if file exists
        if not os.path.exists(filepath):
            self.logger.warning(f"Backup file does not exist: {filepath}")
            return False

        # Check if file is readable
        content = safe_read_file(filepath)
        if content is None:
            self.logger.warning(f"Cannot read backup file: {filepath}")
            return False

        # Check if file has content
        if len(content.strip()) == 0:
            self.logger.warning(f"Backup file is empty: {filepath}")
            return False

        # Check minimum size (should be at least 100 bytes for a valid config)
        if len(content) < 100:
            self.logger.warning(f"Backup file too small: {filepath} ({len(content)} bytes)")
            return False

        # Optional: Check for expected markers
        # This is basic validation - could be enhanced based on device type
        if "# Configuration Backup" not in content:
            self.logger.warning(f"Backup file missing header: {filepath}")
            # Don't fail on this - old backups might not have header

        self.logger.debug(f"Backup verified: {filepath} ({len(content)} bytes)")
        return True

    def generate_backup_report(self, results: List[Dict[str, Any]]) -> str:
        """
        Generate a summary report from backup results.

        Args:
            results: List of result dictionaries from backup operations

        Returns:
            Formatted report string

        Example:
            results = backup_mgr.backup_all_devices()
            report = backup_mgr.generate_backup_report(results)
            print(report)
        """
        if not results:
            return "No backup results to report"

        # Calculate statistics
        total = len(results)
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        success_count = len(successful)
        failed_count = len(failed)

        # Calculate total backup size
        total_size = sum(r.get('file_size', 0) or 0 for r in successful)
        total_size_mb = total_size / (1024 * 1024)

        # Build report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("CONFIGURATION BACKUP REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Timestamp: {get_human_timestamp()}")
        report_lines.append(f"Total devices: {total}")
        report_lines.append(f"Successful: {success_count}")
        report_lines.append(f"Failed: {failed_count}")
        report_lines.append(f"Success rate: {(success_count/total*100):.1f}%")
        report_lines.append(f"Total backup size: {total_size_mb:.2f} MB")
        report_lines.append("")

        # List successful backups
        if successful:
            report_lines.append("-" * 80)
            report_lines.append("SUCCESSFUL BACKUPS")
            report_lines.append("-" * 80)
            for r in successful:
                size_kb = (r.get('file_size', 0) or 0) / 1024
                report_lines.append(
                    f"  ✓ {r['device_name']:<15} → {os.path.basename(r['filepath'])} "
                    f"({size_kb:.1f} KB)"
                )
            report_lines.append("")

        # List failed backups
        if failed:
            report_lines.append("-" * 80)
            report_lines.append("FAILED BACKUPS")
            report_lines.append("-" * 80)
            for r in failed:
                error = r.get('error', 'Unknown error')
                # Truncate long error messages
                if len(error) > 60:
                    error = error[:57] + "..."
                report_lines.append(f"  ✗ {r['device_name']:<15} → {error}")
            report_lines.append("")

        report_lines.append("=" * 80)

        return "\n".join(report_lines)

    def cleanup_old_backups(
        self,
        device_name: Optional[str] = None,
        days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Remove backup files older than retention period.

        Args:
            device_name: Optional device name to cleanup (None for all devices)
            days: Optional days threshold (None to use retention_days)

        Returns:
            Dictionary with cleanup statistics:
                - deleted_count: Number of files deleted
                - deleted_files: List of deleted file paths
                - freed_space: Space freed in bytes
                - errors: List of error messages

        Example:
            # Cleanup all old backups
            result = backup_mgr.cleanup_old_backups()

            # Cleanup old backups for specific device
            result = backup_mgr.cleanup_old_backups(device_name="spine1")

            # Cleanup with custom retention
            result = backup_mgr.cleanup_old_backups(days=7)
        """
        retention = days if days is not None else self.retention_days
        cutoff_date = datetime.now() - timedelta(days=retention)

        self.logger.info(
            f"Starting cleanup of backups older than {retention} days "
            f"(before {cutoff_date.strftime('%Y-%m-%d')})"
        )

        result = {
            'deleted_count': 0,
            'deleted_files': [],
            'freed_space': 0,
            'errors': []
        }

        try:
            # Get list of backups to check
            if device_name:
                backups = self.list_device_backups(device_name)
            else:
                backups = list_files(self.backup_dir, extension=".cfg")

            # Check each backup file
            for filepath in backups:
                try:
                    # Get file modification time
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

                    # Delete if older than cutoff
                    if file_time < cutoff_date:
                        file_size = os.path.getsize(filepath)

                        os.remove(filepath)

                        result['deleted_count'] += 1
                        result['deleted_files'].append(filepath)
                        result['freed_space'] += file_size

                        self.logger.info(f"Deleted old backup: {filepath}")

                except Exception as e:
                    error_msg = f"Failed to delete {filepath}: {e}"
                    self.logger.error(error_msg)
                    result['errors'].append(error_msg)

            freed_mb = result['freed_space'] / (1024 * 1024)
            self.logger.info(
                f"Cleanup complete - Deleted {result['deleted_count']} files, "
                f"freed {freed_mb:.2f} MB"
            )

        except Exception as e:
            error_msg = f"Cleanup failed: {e}"
            self.logger.error(error_msg)
            result['errors'].append(error_msg)

        return result

    def __repr__(self) -> str:
        """Return string representation of ConfigBackup."""
        device_count = self.inventory_loader.get_device_count()
        return (
            f"ConfigBackup(backup_dir='{self.backup_dir}', "
            f"devices={device_count}, retention_days={self.retention_days})"
        )


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of the ConfigBackup class.
    Run this script directly to test backup functionality.
    """
    import sys
    from utils import setup_logging, print_success, print_error, print_info

    # Setup logging
    logger = setup_logging(log_level="INFO")

    try:
        print("=" * 80)
        print("Configuration Backup System - Demo")
        print("=" * 80)
        print()

        # Initialize backup manager
        print_info("Initializing backup manager...")
        backup_mgr = ConfigBackup(
            inventory_path="inventory/devices.yaml",
            backup_dir="configs/backups",
            retention_days=30
        )
        print_success(f"Backup manager initialized: {backup_mgr}")
        print()

        # Display inventory summary
        print_info("Loading device inventory...")
        devices = backup_mgr.inventory_loader.get_all_devices()
        print_success(f"Loaded {len(devices)} devices from inventory")
        print()

        # Example 1: Backup a single device
        print("-" * 80)
        print("EXAMPLE 1: Backup Single Device")
        print("-" * 80)
        spine1 = backup_mgr.inventory_loader.get_device_by_name("spine1")

        if spine1:
            print_info(f"Backing up device: {spine1['name']} ({spine1['ip']})")
            result = backup_mgr.backup_device(spine1)

            if result['success']:
                print_success(
                    f"Backup successful: {os.path.basename(result['filepath'])} "
                    f"({result['file_size']/1024:.1f} KB)"
                )
            else:
                print_error(f"Backup failed: {result['error']}")
        else:
            print_error("Device 'spine1' not found in inventory")

        print()

        # Example 2: Backup devices by role
        print("-" * 80)
        print("EXAMPLE 2: Backup All Spine Devices")
        print("-" * 80)
        print_info("Backing up all spine switches...")
        results = backup_mgr.backup_devices_by_role("spine", parallel=True)

        # Generate and display report
        report = backup_mgr.generate_backup_report(results)
        print(report)

        # Example 3: List backups for a device
        print("-" * 80)
        print("EXAMPLE 3: List Device Backups")
        print("-" * 80)
        device_name = "spine1"
        print_info(f"Listing backups for device '{device_name}'...")

        backups = backup_mgr.list_device_backups(device_name)
        if backups:
            print_success(f"Found {len(backups)} backup(s):")
            for i, backup in enumerate(backups, 1):
                print(f"  {i}. {os.path.basename(backup)}")

            # Show latest backup
            latest = backup_mgr.get_latest_backup(device_name)
            if latest:
                print_info(f"Latest backup: {os.path.basename(latest)}")
        else:
            print_error(f"No backups found for device '{device_name}'")

        print()

        # Example 4: Verify backup
        if backups:
            print("-" * 80)
            print("EXAMPLE 4: Verify Backup")
            print("-" * 80)
            latest = backups[0]
            print_info(f"Verifying backup: {os.path.basename(latest)}")

            if backup_mgr.verify_backup(latest):
                print_success("Backup verification passed")
            else:
                print_error("Backup verification failed")

        print()
        print("=" * 80)
        print("Demo complete!")
        print("=" * 80)

    except FileNotFoundError as e:
        print_error(f"File not found: {e}")
        print("\nMake sure you're running this script from the project root directory.")
        sys.exit(1)

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
