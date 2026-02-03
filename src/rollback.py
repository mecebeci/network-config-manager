import os
import re
import glob
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .connection_manager import ConnectionManager
from .backup import ConfigBackup
from .inventory_loader import InventoryLoader
from .utils import (
    get_logger,
    get_timestamp,
    get_human_timestamp,
    safe_read_file,
    ensure_directory,
    create_progress_bar,
)
from .exceptions import (
    ConnectionError,
    AuthenticationError,
    TimeoutError,
    CommandExecutionError,
    DeviceNotReachableError,
)


class ConfigRollback:
    """
    Configuration rollback system for restoring devices to previous configurations.

    This class provides comprehensive rollback capabilities including:
    - Discovering available backups for devices
    - Previewing backup configurations
    - Safely restoring configurations with pre-rollback safety backups
    - Rolling back multiple devices in parallel or sequentially
    - Rolling back to specific timestamps

    Attributes:
        inventory_loader (InventoryLoader): Inventory management instance
        backup_manager (ConfigBackup): Backup management instance
        backup_dir (str): Directory containing backup files
        logger (logging.Logger): Logger instance for this module
        create_safety_backup (bool): Whether to create safety backup before rollback

    Example:
        from src.rollback import ConfigRollback
        from src.inventory_loader import InventoryLoader

        # Initialize
        rollback_mgr = ConfigRollback()
        inv = InventoryLoader()

        # List available backups for device
        device_name = "spine1"
        backups = rollback_mgr.list_device_backups(device_name)
        for backup in backups:
            print(f"{backup['filename']} - {backup['age']}")

        # Get latest backup
        latest = rollback_mgr.get_latest_backup(device_name)
        print(f"Latest backup: {latest['filename']}")

        # Preview backup
        preview = rollback_mgr.preview_backup(latest['filepath'])
        print(preview)

        # Rollback device
        device = inv.get_device_by_name(device_name)
        result = rollback_mgr.rollback_device(device, latest['filepath'])

        if result['success']:
            print(f"Rollback successful!")
            if result['safety_backup_created']:
                print(f"Safety backup: {result['safety_backup_created']}")
        else:
            print(f"Rollback failed: {result['error']}")
    """

    def __init__(
        self,
        inventory_path: str = "inventory/devices.yaml",
        backup_dir: str = "configs/backups",
        create_safety_backup: bool = True
    ):
        """
        Initialize ConfigRollback manager.

        Args:
            inventory_path: Path to inventory YAML file (default: inventory/devices.yaml)
            backup_dir: Directory containing backups (default: configs/backups)
            create_safety_backup: Create safety backup before rollback (default: True)

        Raises:
            RuntimeError: If backup directory doesn't exist or inventory fails to load

        Example:
            rollback_mgr = ConfigRollback(
                inventory_path="inventory/devices.yaml",
                backup_dir="configs/backups",
                create_safety_backup=True
            )
        """
        self.logger = get_logger(__name__)
        self.backup_dir = backup_dir
        self.create_safety_backup = create_safety_backup

        # Initialize inventory loader
        try:
            self.inventory_loader = InventoryLoader(inventory_path)
            self.logger.info(f"Inventory loaded from {inventory_path}")
        except Exception as e:
            self.logger.error(f"Failed to load inventory: {e}")
            raise RuntimeError(f"Failed to load inventory: {e}")

        # Initialize backup manager
        try:
            self.backup_manager = ConfigBackup(
                inventory_path=inventory_path,
                backup_dir=backup_dir
            )
            self.logger.info("Backup manager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize backup manager: {e}")
            raise RuntimeError(f"Failed to initialize backup manager: {e}")

        # Validate backup directory exists
        if not os.path.exists(backup_dir):
            self.logger.error(f"Backup directory does not exist: {backup_dir}")
            raise RuntimeError(f"Backup directory does not exist: {backup_dir}")

        if not os.path.isdir(backup_dir):
            self.logger.error(f"Backup path is not a directory: {backup_dir}")
            raise RuntimeError(f"Backup path is not a directory: {backup_dir}")

        self.logger.info(
            f"ConfigRollback initialized - Directory: {backup_dir}, "
            f"Safety backup: {create_safety_backup}"
        )

    def _parse_timestamp_from_filename(self, filename: str) -> Optional[datetime]:
        """
        Extract timestamp from backup filename.

        Expected format: {device_name}_{YYYYMMDD_HHMMSS}.cfg

        Args:
            filename: Backup filename (can include path)

        Returns:
            datetime object or None if invalid format

        Example:
            dt = self._parse_timestamp_from_filename("spine1_20250203_143022.cfg")
            # Returns: datetime(2025, 2, 3, 14, 30, 22)
        """
        try:
            # Extract just the filename if full path provided
            basename = os.path.basename(filename)

            # Pattern: devicename_YYYYMMDD_HHMMSS.cfg
            pattern = r'.*_(\d{8})_(\d{6})\.cfg$'
            match = re.match(pattern, basename)

            if match:
                date_str = match.group(1)  # YYYYMMDD
                time_str = match.group(2)  # HHMMSS

                # Parse into datetime
                timestamp_str = f"{date_str}_{time_str}"
                dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                return dt
            else:
                self.logger.debug(f"Filename doesn't match expected pattern: {basename}")
                return None

        except Exception as e:
            self.logger.debug(f"Failed to parse timestamp from {filename}: {e}")
            return None

    def _format_file_size(self, size_bytes: int) -> str:
        """
        Convert bytes to human-readable format.

        Args:
            size_bytes: File size in bytes

        Returns:
            Formatted string (e.g., "1.5 KB", "2.3 MB")

        Example:
            size = self._format_file_size(1536)
            # Returns: "1.5 KB"
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    def _calculate_age(self, backup_datetime: datetime) -> str:
        """
        Calculate how old a backup is.

        Args:
            backup_datetime: Datetime of the backup

        Returns:
            Human-readable age string (e.g., "2 hours ago", "3 days ago")

        Example:
            age = self._calculate_age(datetime(2025, 2, 1, 12, 0, 0))
            # Returns: "2 days ago"
        """
        now = datetime.now()
        delta = now - backup_datetime

        # Handle future timestamps (shouldn't happen, but just in case)
        if delta.total_seconds() < 0:
            return "in the future"

        seconds = delta.total_seconds()

        if seconds < 60:
            return f"{int(seconds)} seconds ago"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:  # 7 days
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:  # 30 days
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        else:
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"

    def _validate_backup_file(self, filepath: str) -> Tuple[bool, str]:
        """
        Validate backup file before using.

        Checks:
        - File exists
        - File is readable
        - File is not empty
        - File contains valid content

        Args:
            filepath: Path to backup file

        Returns:
            Tuple of (is_valid, message)

        Example:
            valid, msg = self._validate_backup_file("configs/backups/spine1_20250203_143022.cfg")
            if valid:
                print("Backup is valid")
            else:
                print(f"Backup invalid: {msg}")
        """
        # Check if file exists
        if not os.path.exists(filepath):
            return False, f"File does not exist: {filepath}"

        # Check if path is a file (not directory)
        if not os.path.isfile(filepath):
            return False, f"Path is not a file: {filepath}"

        # Check if file is readable
        if not os.access(filepath, os.R_OK):
            return False, f"File is not readable: {filepath}"

        # Check file size
        try:
            file_size = os.path.getsize(filepath)
            if file_size == 0:
                return False, "File is empty"

            if file_size < 50:
                return False, f"File too small ({file_size} bytes)"

        except Exception as e:
            return False, f"Cannot get file size: {e}"

        # Try reading content
        content = safe_read_file(filepath)
        if content is None:
            return False, "Cannot read file content"

        if len(content.strip()) == 0:
            return False, "File contains no content"

        # Optional: Check for expected markers (basic validation)
        # This is lenient - old backups might not have header
        if len(content) < 50:
            return False, "File content too short to be valid configuration"

        return True, "Valid"

    def list_device_backups(self, device_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List all backup files for specific device.

        Args:
            device_name: Name of the device
            limit: Maximum number of results to return (0 for unlimited)

        Returns:
            List of backup info dictionaries sorted by timestamp (newest first)

        Example:
            backups = rollback_mgr.list_device_backups("spine1", limit=5)
            for backup in backups:
                print(f"{backup['filename']} - {backup['age']} - {backup['size_readable']}")
        """
        self.logger.debug(f"Listing backups for device '{device_name}' (limit={limit})")

        try:
            # Search for backup files matching pattern: {device_name}_*.cfg
            pattern = os.path.join(self.backup_dir, f"{device_name}_*.cfg")
            backup_files = glob.glob(pattern)

            if not backup_files:
                self.logger.debug(f"No backups found for device '{device_name}'")
                return []

            # Parse and collect backup info
            backups = []
            for filepath in backup_files:
                filename = os.path.basename(filepath)

                # Parse timestamp from filename
                timestamp_dt = self._parse_timestamp_from_filename(filename)
                if timestamp_dt is None:
                    self.logger.warning(f"Skipping file with invalid format: {filename}")
                    continue

                # Get file size
                try:
                    size_bytes = os.path.getsize(filepath)
                except Exception as e:
                    self.logger.warning(f"Cannot get size for {filepath}: {e}")
                    continue

                # Build backup info dict
                backup_info = {
                    'filepath': filepath,
                    'filename': filename,
                    'timestamp': timestamp_dt.strftime("%Y%m%d_%H%M%S"),
                    'timestamp_readable': timestamp_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    'size': size_bytes,
                    'size_readable': self._format_file_size(size_bytes),
                    'age': self._calculate_age(timestamp_dt),
                    '_timestamp_dt': timestamp_dt  # For sorting
                }
                backups.append(backup_info)

            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x['_timestamp_dt'], reverse=True)

            # Remove internal sorting key
            for backup in backups:
                del backup['_timestamp_dt']

            # Apply limit if specified
            if limit > 0:
                backups = backups[:limit]

            self.logger.debug(f"Found {len(backups)} backups for device '{device_name}'")
            return backups

        except Exception as e:
            self.logger.error(f"Failed to list backups for '{device_name}': {e}")
            return []

    def get_backup_info(self, backup_filepath: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from backup file.

        Args:
            backup_filepath: Path to backup file

        Returns:
            Dictionary with backup metadata, or None if file doesn't exist

        Example:
            info = rollback_mgr.get_backup_info("configs/backups/spine1_20250203_143022.cfg")
            if info:
                print(f"Device: {info['device_name']}")
                print(f"Timestamp: {info['timestamp_readable']}")
                print(f"Size: {info['size_readable']}")
        """
        self.logger.debug(f"Getting backup info for: {backup_filepath}")

        # Check if file exists
        if not os.path.exists(backup_filepath):
            self.logger.warning(f"Backup file not found: {backup_filepath}")
            return None

        try:
            filename = os.path.basename(backup_filepath)

            # Extract device name from filename (everything before first underscore followed by date)
            # Pattern: devicename_YYYYMMDD_HHMMSS.cfg
            match = re.match(r'^(.+?)_(\d{8}_\d{6})\.cfg$', filename)
            if match:
                device_name = match.group(1)
                timestamp_str = match.group(2)
            else:
                # Fallback: just take everything before .cfg
                device_name = filename.replace('.cfg', '')
                timestamp_str = "unknown"

            # Parse timestamp
            timestamp_dt = self._parse_timestamp_from_filename(filename)

            # Get file info
            size_bytes = os.path.getsize(backup_filepath)
            mod_time = datetime.fromtimestamp(os.path.getmtime(backup_filepath))

            # Build info dict
            info = {
                'filepath': backup_filepath,
                'filename': filename,
                'device_name': device_name,
                'size': size_bytes,
                'size_readable': self._format_file_size(size_bytes),
                'modified': mod_time.strftime("%Y-%m-%d %H:%M:%S")
            }

            # Add timestamp info if parsed successfully
            if timestamp_dt:
                info['timestamp'] = timestamp_dt.strftime("%Y%m%d_%H%M%S")
                info['timestamp_readable'] = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
                info['age'] = self._calculate_age(timestamp_dt)
            else:
                info['timestamp'] = "unknown"
                info['timestamp_readable'] = "unknown"
                info['age'] = "unknown"

            return info

        except Exception as e:
            self.logger.error(f"Failed to get backup info for {backup_filepath}: {e}")
            return None

    def get_latest_backup(self, device_name: str) -> Optional[Dict[str, Any]]:
        """
        Get most recent backup for device.

        Args:
            device_name: Name of the device

        Returns:
            Backup info dictionary or None if no backups found

        Example:
            latest = rollback_mgr.get_latest_backup("spine1")
            if latest:
                print(f"Latest: {latest['filename']}")
                print(f"Age: {latest['age']}")
            else:
                print("No backups found")
        """
        self.logger.debug(f"Getting latest backup for device '{device_name}'")

        backups = self.list_device_backups(device_name, limit=1)

        if backups:
            latest = backups[0]
            self.logger.debug(f"Latest backup for '{device_name}': {latest['filename']}")
            return latest
        else:
            self.logger.debug(f"No backups found for device '{device_name}'")
            return None

    def preview_backup(self, backup_filepath: str, lines: int = 50) -> str:
        """
        Preview backup file contents.

        Args:
            backup_filepath: Path to backup file
            lines: Number of lines to preview (default: 50)

        Returns:
            Formatted preview string

        Example:
            preview = rollback_mgr.preview_backup("configs/backups/spine1_20250203_143022.cfg", lines=30)
            print(preview)
        """
        self.logger.debug(f"Previewing backup: {backup_filepath} (lines={lines})")

        # Validate file
        valid, msg = self._validate_backup_file(backup_filepath)
        if not valid:
            error_msg = f"Cannot preview backup: {msg}"
            self.logger.error(error_msg)
            return error_msg

        try:
            # Read file content
            content = safe_read_file(backup_filepath)
            if content is None:
                return f"Error: Cannot read file {backup_filepath}"

            # Split into lines
            content_lines = content.splitlines()
            total_lines = len(content_lines)

            # Get backup info for header
            info = self.get_backup_info(backup_filepath)

            # Build preview
            preview_lines = []
            preview_lines.append("=" * 80)
            preview_lines.append("BACKUP PREVIEW")
            preview_lines.append("=" * 80)

            if info:
                preview_lines.append(f"File: {info['filename']}")
                preview_lines.append(f"Device: {info['device_name']}")
                preview_lines.append(f"Timestamp: {info.get('timestamp_readable', 'unknown')}")
                preview_lines.append(f"Size: {info['size_readable']}")
                preview_lines.append(f"Age: {info.get('age', 'unknown')}")
            else:
                preview_lines.append(f"File: {os.path.basename(backup_filepath)}")

            preview_lines.append("=" * 80)
            preview_lines.append("")

            # Add preview lines
            preview_lines.append(f"Showing first {min(lines, total_lines)} of {total_lines} lines:")
            preview_lines.append("-" * 80)

            for i, line in enumerate(content_lines[:lines], start=1):
                preview_lines.append(f"{i:4d} | {line}")

            if total_lines > lines:
                preview_lines.append("-" * 80)
                preview_lines.append(f"... {total_lines - lines} more lines ...")

            preview_lines.append("")
            preview_lines.append("=" * 80)

            return "\n".join(preview_lines)

        except Exception as e:
            error_msg = f"Error previewing backup: {e}"
            self.logger.error(error_msg)
            return error_msg

    def compare_backups(self, backup1: str, backup2: str) -> str:
        """
        Compare two backup files.

        Shows differences between configurations using simple line-by-line comparison.

        Args:
            backup1: Path to first backup file
            backup2: Path to second backup file

        Returns:
            Formatted comparison string

        Example:
            comparison = rollback_mgr.compare_backups(
                "configs/backups/spine1_20250203_143022.cfg",
                "configs/backups/spine1_20250202_103015.cfg"
            )
            print(comparison)
        """
        self.logger.debug(f"Comparing backups: {backup1} vs {backup2}")

        # Validate both files
        valid1, msg1 = self._validate_backup_file(backup1)
        valid2, msg2 = self._validate_backup_file(backup2)

        if not valid1:
            return f"Error: First backup invalid: {msg1}"
        if not valid2:
            return f"Error: Second backup invalid: {msg2}"

        try:
            # Read both files
            content1 = safe_read_file(backup1)
            content2 = safe_read_file(backup2)

            if content1 is None or content2 is None:
                return "Error: Cannot read one or both backup files"

            # Get info for headers
            info1 = self.get_backup_info(backup1)
            info2 = self.get_backup_info(backup2)

            # Split into lines
            lines1 = content1.splitlines()
            lines2 = content2.splitlines()

            # Build comparison output
            result = []
            result.append("=" * 80)
            result.append("BACKUP COMPARISON")
            result.append("=" * 80)
            result.append("")
            result.append(f"Backup 1: {info1['filename'] if info1 else os.path.basename(backup1)}")
            if info1:
                result.append(f"  Timestamp: {info1.get('timestamp_readable', 'unknown')}")
                result.append(f"  Size: {info1['size_readable']}")
            result.append("")
            result.append(f"Backup 2: {info2['filename'] if info2 else os.path.basename(backup2)}")
            if info2:
                result.append(f"  Timestamp: {info2.get('timestamp_readable', 'unknown')}")
                result.append(f"  Size: {info2['size_readable']}")
            result.append("")
            result.append("=" * 80)
            result.append("")

            # Simple line-by-line comparison
            # Find differences
            lines1_set = set(lines1)
            lines2_set = set(lines2)

            only_in_1 = lines1_set - lines2_set
            only_in_2 = lines2_set - lines1_set

            if not only_in_1 and not only_in_2:
                result.append("Files are identical")
            else:
                result.append(f"Lines only in Backup 1: {len(only_in_1)}")
                result.append(f"Lines only in Backup 2: {len(only_in_2)}")
                result.append("")

                if only_in_1:
                    result.append("Lines only in Backup 1:")
                    result.append("-" * 80)
                    for line in list(only_in_1)[:20]:  # Limit to first 20
                        result.append(f"  - {line}")
                    if len(only_in_1) > 20:
                        result.append(f"  ... and {len(only_in_1) - 20} more lines")
                    result.append("")

                if only_in_2:
                    result.append("Lines only in Backup 2:")
                    result.append("-" * 80)
                    for line in list(only_in_2)[:20]:  # Limit to first 20
                        result.append(f"  + {line}")
                    if len(only_in_2) > 20:
                        result.append(f"  ... and {len(only_in_2) - 20} more lines")
                    result.append("")

            result.append("=" * 80)

            return "\n".join(result)

        except Exception as e:
            error_msg = f"Error comparing backups: {e}"
            self.logger.error(error_msg)
            return error_msg

    def rollback_device(
        self,
        device: Dict[str, Any],
        backup_filepath: str,
        safety_backup: Optional[bool] = None,
        verify: bool = True
    ) -> Dict[str, Any]:
        """
        Restore configuration from backup file.

        Args:
            device: Device dictionary from inventory
            backup_filepath: Path to backup file to restore
            safety_backup: Override create_safety_backup setting (None to use default)
            verify: Verify backup file before restoring (default: True)

        Returns:
            Result dictionary with keys:
                - success (bool): Whether rollback succeeded
                - device_name (str): Device name
                - backup_file_used (str): Path to backup file used
                - safety_backup_created (str or None): Path to safety backup if created
                - timestamp (str): Timestamp of rollback operation
                - error (str or None): Error message if failed

        Example:
            device = inventory_loader.get_device_by_name("spine1")
            result = rollback_mgr.rollback_device(
                device,
                "configs/backups/spine1_20250203_143022.cfg",
                safety_backup=True,
                verify=True
            )

            if result['success']:
                print("Rollback successful!")
            else:
                print(f"Rollback failed: {result['error']}")
        """
        device_name = device.get('name', device.get('ip', 'unknown'))
        result = {
            'success': False,
            'device_name': device_name,
            'backup_file_used': backup_filepath,
            'safety_backup_created': None,
            'timestamp': get_human_timestamp(),
            'error': None
        }

        self.logger.info(f"Starting rollback for device '{device_name}' from {backup_filepath}")

        try:
            # Determine if safety backup should be created
            do_safety_backup = safety_backup if safety_backup is not None else self.create_safety_backup

            # Validate backup file if requested
            if verify:
                self.logger.debug(f"Verifying backup file: {backup_filepath}")
                valid, msg = self._validate_backup_file(backup_filepath)
                if not valid:
                    error_msg = f"Backup validation failed: {msg}"
                    self.logger.error(error_msg)
                    result['error'] = error_msg
                    return result

            # Read backup configuration
            self.logger.debug(f"Reading backup configuration from {backup_filepath}")
            backup_config = safe_read_file(backup_filepath)

            if backup_config is None:
                error_msg = f"Cannot read backup file: {backup_filepath}"
                self.logger.error(error_msg)
                result['error'] = error_msg
                return result

            # Remove metadata header lines if present
            config_lines = []
            in_header = True
            for line in backup_config.splitlines():
                if in_header and line.startswith('#'):
                    continue
                elif in_header and line.strip() == '':
                    continue
                else:
                    in_header = False
                    config_lines.append(line)

            clean_config = '\n'.join(config_lines)

            if not clean_config.strip():
                error_msg = "Backup file contains no configuration data"
                self.logger.error(error_msg)
                result['error'] = error_msg
                return result

            # Create safety backup before rollback
            if do_safety_backup:
                self.logger.info(f"Creating safety backup for '{device_name}' before rollback")
                try:
                    safety_result = self.backup_manager.backup_device(device, verify=False)
                    if safety_result['success']:
                        result['safety_backup_created'] = safety_result['filepath']
                        self.logger.info(f"Safety backup created: {safety_result['filepath']}")
                    else:
                        # Log warning but don't fail the rollback
                        self.logger.warning(
                            f"Failed to create safety backup: {safety_result.get('error', 'unknown error')}"
                        )
                except Exception as e:
                    self.logger.warning(f"Exception creating safety backup: {e}")

            # Merge device settings with global settings
            device_config = self.backup_manager._merge_device_settings(device)

            # Connect to device and apply configuration
            self.logger.info(f"Connecting to device '{device_name}' to apply rollback")

            with ConnectionManager(device_config) as conn:
                self.logger.info(f"Connected to '{device_name}', applying configuration")

                # Split config into individual commands if needed
                # For SR Linux/Nokia devices, we can send the full config
                device_type = device_config.get('device_type', 'nokia_sros')

                try:
                    # Apply configuration
                    if device_type in ['nokia_sros', 'sr_linux']:
                        # For SR Linux, use "enter candidate" mode
                        # This is a simplified approach - production systems may need more sophisticated handling
                        self.logger.debug("Applying configuration to SR Linux device")
                        output = conn.send_config(clean_config.splitlines())
                    else:
                        # For other devices, send as config commands
                        self.logger.debug("Applying configuration to device")
                        output = conn.send_config(clean_config.splitlines())

                    self.logger.info(f"Configuration applied successfully to '{device_name}'")
                    self.logger.debug(f"Device output: {output[:200]}...")  # Log first 200 chars

                    result['success'] = True

                except CommandExecutionError as e:
                    error_msg = f"Failed to apply configuration: {str(e)}"
                    self.logger.error(f"Device '{device_name}': {error_msg}")
                    result['error'] = error_msg
                    return result

        except (ConnectionError, AuthenticationError, DeviceNotReachableError) as e:
            error_msg = f"Connection failed: {str(e)}"
            self.logger.error(f"Device '{device_name}': {error_msg}")
            result['error'] = error_msg

        except Exception as e:
            error_msg = f"Unexpected error during rollback: {str(e)}"
            self.logger.error(f"Device '{device_name}': {error_msg}")
            result['error'] = error_msg

        if result['success']:
            self.logger.info(f"Rollback completed successfully for '{device_name}'")
        else:
            self.logger.error(f"Rollback failed for '{device_name}': {result.get('error', 'unknown')}")

        return result

    def rollback_multiple_devices(
        self,
        devices_and_backups: List[Tuple[Dict[str, Any], str]],
        parallel: bool = False,
        max_workers: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Rollback multiple devices.

        Args:
            devices_and_backups: List of tuples [(device, backup_filepath), ...]
            parallel: Enable concurrent rollback (default: False)
            max_workers: Maximum number of parallel workers (default: 5)

        Returns:
            List of result dictionaries from rollback_device()

        Example:
            devices_and_backups = [
                (device1, "configs/backups/spine1_20250203_143022.cfg"),
                (device2, "configs/backups/spine2_20250203_143025.cfg")
            ]
            results = rollback_mgr.rollback_multiple_devices(
                devices_and_backups,
                parallel=True,
                max_workers=3
            )
        """
        if not devices_and_backups:
            self.logger.warning("No devices provided for rollback")
            return []

        device_count = len(devices_and_backups)
        self.logger.info(
            f"Starting rollback for {device_count} devices "
            f"(mode: {'parallel' if parallel else 'sequential'})"
        )

        results = []

        if parallel:
            # Parallel execution using ThreadPoolExecutor
            self.logger.info(f"Using {max_workers} parallel workers")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all rollback tasks
                future_to_device = {
                    executor.submit(self.rollback_device, device, backup_path): device
                    for device, backup_path in devices_and_backups
                }

                # Process results as they complete with progress indicator
                for future in create_progress_bar(
                    as_completed(future_to_device),
                    description="Rolling back devices",
                    total=device_count
                ):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        device = future_to_device[future]
                        device_name = device.get('name', 'unknown')
                        self.logger.error(f"Rollback task failed for {device_name}: {e}")
                        results.append({
                            'success': False,
                            'device_name': device_name,
                            'backup_file_used': None,
                            'safety_backup_created': None,
                            'timestamp': get_human_timestamp(),
                            'error': str(e)
                        })

        else:
            # Sequential execution
            for device, backup_path in create_progress_bar(
                devices_and_backups,
                description="Rolling back devices"
            ):
                result = self.rollback_device(device, backup_path)
                results.append(result)

        # Log summary
        success_count = sum(1 for r in results if r['success'])
        failed_count = device_count - success_count

        self.logger.info(
            f"Rollback complete - Total: {device_count}, "
            f"Success: {success_count}, Failed: {failed_count}"
        )

        return results

    def rollback_to_timestamp(
        self,
        device: Dict[str, Any],
        target_datetime: datetime
    ) -> Dict[str, Any]:
        """
        Rollback to backup closest to target datetime.

        Args:
            device: Device dictionary from inventory
            target_datetime: Target datetime to rollback to

        Returns:
            Result dictionary from rollback_device(), or error if no backup found

        Example:
            from datetime import datetime

            device = inventory_loader.get_device_by_name("spine1")
            target = datetime(2025, 2, 2, 12, 0, 0)
            result = rollback_mgr.rollback_to_timestamp(device, target)

            if result['success']:
                print("Rolled back to backup near target time")
        """
        device_name = device.get('name', device.get('ip', 'unknown'))

        self.logger.info(
            f"Finding backup for '{device_name}' closest to {target_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # Get all backups for device
        backups = self.list_device_backups(device_name, limit=0)  # Get all backups

        if not backups:
            error_msg = f"No backups found for device '{device_name}'"
            self.logger.error(error_msg)
            return {
                'success': False,
                'device_name': device_name,
                'backup_file_used': None,
                'safety_backup_created': None,
                'timestamp': get_human_timestamp(),
                'error': error_msg
            }

        # Find backup closest to target datetime
        closest_backup = None
        min_diff = None

        for backup in backups:
            # Parse timestamp
            backup_dt = self._parse_timestamp_from_filename(backup['filename'])
            if backup_dt is None:
                continue

            # Calculate time difference
            diff = abs((backup_dt - target_datetime).total_seconds())

            if min_diff is None or diff < min_diff:
                min_diff = diff
                closest_backup = backup

        if closest_backup is None:
            error_msg = f"Could not find valid backup for device '{device_name}'"
            self.logger.error(error_msg)
            return {
                'success': False,
                'device_name': device_name,
                'backup_file_used': None,
                'safety_backup_created': None,
                'timestamp': get_human_timestamp(),
                'error': error_msg
            }

        self.logger.info(
            f"Found backup closest to target: {closest_backup['filename']} "
            f"(timestamp: {closest_backup['timestamp_readable']})"
        )

        # Perform rollback
        return self.rollback_device(device, closest_backup['filepath'])

    def generate_rollback_report(self, results: List[Dict[str, Any]]) -> str:
        """
        Generate summary report from rollback results.

        Args:
            results: List of result dictionaries from rollback operations

        Returns:
            Formatted report string

        Example:
            results = rollback_mgr.rollback_multiple_devices(devices_and_backups)
            report = rollback_mgr.generate_rollback_report(results)
            print(report)
        """
        if not results:
            return "No rollback results to report"

        # Calculate statistics
        total = len(results)
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]

        success_count = len(successful)
        failed_count = len(failed)

        # Count safety backups created
        safety_backups = sum(1 for r in successful if r.get('safety_backup_created'))

        # Build report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("CONFIGURATION ROLLBACK REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Timestamp: {get_human_timestamp()}")
        report_lines.append(f"Total devices: {total}")
        report_lines.append(f"Successful: {success_count}")
        report_lines.append(f"Failed: {failed_count}")
        report_lines.append(f"Success rate: {(success_count/total*100):.1f}%")
        report_lines.append(f"Safety backups created: {safety_backups}")
        report_lines.append("")

        # List successful rollbacks
        if successful:
            report_lines.append("-" * 80)
            report_lines.append("SUCCESSFUL ROLLBACKS")
            report_lines.append("-" * 80)
            for r in successful:
                backup_file = os.path.basename(r['backup_file_used'])
                line = f"  ✓ {r['device_name']:<15} ← {backup_file}"
                if r.get('safety_backup_created'):
                    safety_file = os.path.basename(r['safety_backup_created'])
                    line += f" (safety: {safety_file})"
                report_lines.append(line)
            report_lines.append("")

        # List failed rollbacks
        if failed:
            report_lines.append("-" * 80)
            report_lines.append("FAILED ROLLBACKS")
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

    def __repr__(self) -> str:
        """Return string representation of ConfigRollback."""
        device_count = self.inventory_loader.get_device_count()
        return (
            f"ConfigRollback(backup_dir='{self.backup_dir}', "
            f"devices={device_count}, safety_backup={self.create_safety_backup})"
        )


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of the ConfigRollback class.
    Run this script directly to test rollback functionality.
    """
    import sys
    from .utils import setup_logging, print_success, print_error, print_info

    # Setup logging
    logger = setup_logging(log_level="INFO")

    try:
        print("=" * 80)
        print("Configuration Rollback System - Demo")
        print("=" * 80)
        print()

        # Initialize rollback manager
        print_info("Initializing rollback manager...")
        rollback_mgr = ConfigRollback(
            inventory_path="inventory/devices.yaml",
            backup_dir="configs/backups",
            create_safety_backup=True
        )
        print_success(f"Rollback manager initialized: {rollback_mgr}")
        print()

        # Example 1: List backups for a device
        print("-" * 80)
        print("EXAMPLE 1: List Device Backups")
        print("-" * 80)
        device_name = "spine1"
        print_info(f"Listing backups for device '{device_name}'...")

        backups = rollback_mgr.list_device_backups(device_name, limit=5)
        if backups:
            print_success(f"Found {len(backups)} backup(s):")
            for i, backup in enumerate(backups, 1):
                print(
                    f"  {i}. {backup['filename']} - "
                    f"{backup['age']} - {backup['size_readable']}"
                )
        else:
            print_error(f"No backups found for device '{device_name}'")

        print()

        # Example 2: Get latest backup
        if backups:
            print("-" * 80)
            print("EXAMPLE 2: Get Latest Backup")
            print("-" * 80)
            latest = rollback_mgr.get_latest_backup(device_name)
            if latest:
                print_success(f"Latest backup: {latest['filename']}")
                print(f"  Timestamp: {latest['timestamp_readable']}")
                print(f"  Age: {latest['age']}")
                print(f"  Size: {latest['size_readable']}")
            print()

            # Example 3: Preview backup
            print("-" * 80)
            print("EXAMPLE 3: Preview Backup")
            print("-" * 80)
            preview = rollback_mgr.preview_backup(latest['filepath'], lines=20)
            print(preview)
            print()

        # Example 4: Validate backup
        if backups:
            print("-" * 80)
            print("EXAMPLE 4: Validate Backup")
            print("-" * 80)
            latest = backups[0]
            valid, msg = rollback_mgr._validate_backup_file(latest['filepath'])
            if valid:
                print_success(f"Backup validation passed: {msg}")
            else:
                print_error(f"Backup validation failed: {msg}")
            print()

        print("=" * 80)
        print("Demo complete!")
        print("=" * 80)
        print()
        print_info("To perform actual rollback, use the rollback_device() method")
        print_info("with a device dictionary from inventory")

    except FileNotFoundError as e:
        print_error(f"File not found: {e}")
        print("\nMake sure you're running this script from the project root directory.")
        sys.exit(1)

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
