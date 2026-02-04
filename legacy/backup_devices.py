import argparse
import sys
import os
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Add project root to Python path to enable imports
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import from src module
from src.backup import ConfigBackup
from src.inventory_loader import InventoryLoader
from src.utils import (
    setup_logging,
    get_logger,
    print_info,
    print_success,
    print_error,
    print_separator,
    format_device_list,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def display_backup_plan(devices: List[Dict[str, Any]], parallel: bool, backup_dir: str) -> None:
    """
    Display backup plan before execution.

    Args:
        devices: List of devices to backup
        parallel: Whether parallel execution is enabled
        backup_dir: Backup directory path
    """
    print_separator()
    print("BACKUP PLAN")
    print_separator()

    print(f"\nDevices to backup: {len(devices)}")
    print(f"Execution mode: {'Parallel' if parallel else 'Sequential'}")
    print(f"Backup directory: {backup_dir}")
    print()

    # Display device table
    if devices:
        print("Device List:")
        print(format_device_list(devices))
    print()


def display_results(results: List[Dict[str, Any]], start_time: datetime) -> None:
    """
    Display backup results summary.

    Args:
        results: List of backup result dictionaries
        start_time: Backup start time
    """
    print()
    print_separator()
    print("BACKUP RESULTS")
    print_separator()
    print()

    # Calculate statistics
    total = len(results)
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    success_count = len(successful)
    failed_count = len(failed)

    # Calculate total backup size
    total_size = sum(r.get('file_size', 0) or 0 for r in successful)
    total_size_mb = total_size / (1024 * 1024)

    # Calculate execution time
    execution_time = datetime.now() - start_time

    # Display summary
    print(f"Total devices: {total}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    if total > 0:
        print(f"Success rate: {(success_count/total*100):.1f}%")
    print(f"Total backup size: {total_size_mb:.2f} MB")
    print(f"Execution time: {execution_time.total_seconds():.1f} seconds")
    print()

    # Display successful backups
    if successful:
        print_separator(char="-", length=80)
        print("SUCCESSFUL BACKUPS")
        print_separator(char="-", length=80)
        for r in successful:
            size_kb = (r.get('file_size', 0) or 0) / 1024
            filename = os.path.basename(r['filepath']) if r['filepath'] else 'N/A'
            print_success(f"{r['device_name']:<15} -> {filename} ({size_kb:.1f} KB)")
        print()

    # Display failed backups
    if failed:
        print_separator(char="-", length=80)
        print("FAILED BACKUPS")
        print_separator(char="-", length=80)
        for r in failed:
            error = r.get('error', 'Unknown error')
            # Truncate long error messages
            if len(error) > 60:
                error = error[:57] + "..."
            print_error(f"{r['device_name']:<15} -> {error}")
        print()

    print_separator()


def get_devices_from_args(
    args: argparse.Namespace,
    inventory_loader: InventoryLoader
) -> List[Dict[str, Any]]:
    """
    Determine which devices to backup based on CLI arguments.

    Args:
        args: Parsed command-line arguments
        inventory_loader: InventoryLoader instance

    Returns:
        List of devices to backup

    Raises:
        SystemExit: If invalid device names are specified
    """
    devices = []

    # If specific devices requested
    if args.device:
        # Flatten the list (handle both append and nargs='+')
        device_names = []
        for item in args.device:
            if isinstance(item, list):
                device_names.extend(item)
            else:
                device_names.append(item)

        # Get each device by name
        for name in device_names:
            device = inventory_loader.get_device_by_name(name)
            if device:
                devices.append(device)
            else:
                print_error(f"Device '{name}' not found in inventory")
                print_info("Available devices:")
                all_devices = inventory_loader.get_all_devices()
                for d in all_devices:
                    print(f"  - {d['name']}")
                sys.exit(2)

    # If role filter requested
    elif args.role:
        devices = inventory_loader.get_devices_by_role(args.role)
        if not devices:
            print_error(f"No devices found with role '{args.role}'")
            print_info("Available roles:")
            all_devices = inventory_loader.get_all_devices()
            roles = set(d.get('role', 'unknown') for d in all_devices)
            for role in sorted(roles):
                role_devices = inventory_loader.get_devices_by_role(role)
                print(f"  - {role} ({len(role_devices)} devices)")
            sys.exit(2)

    # Default: backup all devices
    else:
        devices = inventory_loader.get_all_devices()

    return devices


def confirm_backup(device_count: int, parallel: bool) -> bool:
    """
    Ask user to confirm backup operation.

    Args:
        device_count: Number of devices to backup
        parallel: Whether parallel mode is enabled

    Returns:
        True if user confirms, False otherwise
    """
    mode = "parallel" if parallel else "sequential"

    try:
        response = input(f"\nProceed with {mode} backup of {device_count} device(s)? [Y/n]: ")
        return response.lower() in ['', 'y', 'yes']
    except (EOFError, KeyboardInterrupt):
        print()
        return False


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 for success, 1 for failures, 2 for errors)
    """
    # ========================================================================
    # 1. Parse arguments
    # ========================================================================
    parser = argparse.ArgumentParser(
        description="Network Device Configuration Backup Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all
      Backup all devices in parallel

  %(prog)s --device spine1 --device leaf1
      Backup specific devices

  %(prog)s --role spine --no-parallel
      Backup all spine devices sequentially

  %(prog)s --all --verbose
      Backup with verbose output

  %(prog)s --all --backup-dir /tmp/backups
      Backup to custom directory

  %(prog)s --all --quiet
      Quiet mode (only show errors)
        """
    )

    # Device selection arguments
    device_group = parser.add_argument_group('Device Selection')
    device_group.add_argument(
        '--device', '-d',
        action='append',
        metavar='NAME',
        help='Backup specific device(s) by name (can be specified multiple times)'
    )
    device_group.add_argument(
        '--role', '-r',
        metavar='ROLE',
        help='Backup all devices with specific role (e.g., spine, leaf)'
    )
    device_group.add_argument(
        '--all', '-a',
        action='store_true',
        help='Backup all devices in inventory (default if no filters specified)'
    )

    # Execution options
    exec_group = parser.add_argument_group('Execution Options')
    exec_group.add_argument(
        '--parallel',
        action='store_true',
        default=True,
        dest='parallel',
        help='Enable parallel execution (default)'
    )
    exec_group.add_argument(
        '--no-parallel',
        action='store_false',
        dest='parallel',
        help='Disable parallel execution (sequential mode)'
    )
    exec_group.add_argument(
        '--backup-dir',
        metavar='PATH',
        default='configs/backups',
        help='Custom backup directory path (default: configs/backups)'
    )
    exec_group.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )

    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output (show detailed progress and debug info)'
    )
    output_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output (only show errors)'
    )

    # Parse arguments
    args = parser.parse_args()

    # Validate mutually exclusive options
    if args.verbose and args.quiet:
        parser.error("--verbose and --quiet cannot be used together")

    if args.device and args.role:
        parser.error("--device and --role cannot be used together")

    # ========================================================================
    # 2. Setup logging based on verbose/quiet flags
    # ========================================================================
    if args.verbose:
        log_level = "DEBUG"
    elif args.quiet:
        log_level = "ERROR"
    else:
        log_level = "INFO"

    try:
        setup_logging(log_level=log_level)
        logger = get_logger(__name__)
    except Exception as e:
        print(f"Warning: Failed to setup logging: {e}", file=sys.stderr)
        logger = None

    # ========================================================================
    # 3. Initialize ConfigBackup
    # ========================================================================
    try:
        if not args.quiet:
            print_info("Initializing backup system...")

        backup_mgr = ConfigBackup(
            inventory_path="inventory/devices.yaml",
            backup_dir=args.backup_dir,
            retention_days=30
        )

        if not args.quiet:
            print_success("Backup system initialized")

    except FileNotFoundError as e:
        print_error(f"Inventory file not found: {e}")
        print_info("Make sure you're running from the project root directory")
        return 2

    except Exception as e:
        print_error(f"Failed to initialize backup system: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2

    # ========================================================================
    # 4. Load inventory and determine which devices to backup
    # ========================================================================
    try:
        if not args.quiet:
            print_info("Loading device inventory...")

        devices = get_devices_from_args(args, backup_mgr.inventory_loader)

        if not devices:
            print_error("No devices found to backup")
            return 2

        if not args.quiet:
            print_success(f"Loaded {len(devices)} device(s)")

    except SystemExit:
        raise  # Re-raise exit from get_devices_from_args

    except Exception as e:
        print_error(f"Failed to load devices: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2

    # ========================================================================
    # 5. Display backup plan
    # ========================================================================
    if not args.quiet:
        display_backup_plan(devices, args.parallel, args.backup_dir)

    # ========================================================================
    # 6. Confirm if multiple devices (unless --yes flag)
    # ========================================================================
    if not args.yes and len(devices) > 1 and not args.quiet:
        if not confirm_backup(len(devices), args.parallel):
            print_info("Backup cancelled by user")
            return 0

    # ========================================================================
    # 7. Execute backups
    # ========================================================================
    try:
        if not args.quiet:
            print_info(f"Starting backup operation...")

        start_time = datetime.now()

        # Execute backup
        if len(devices) == 1:
            # Single device backup
            result = backup_mgr.backup_device(devices[0])
            results = [result]
        else:
            # Multiple devices backup
            results = backup_mgr.backup_multiple_devices(
                devices,
                parallel=args.parallel
            )

    except KeyboardInterrupt:
        print()
        print_error("Backup interrupted by user")
        return 1

    except Exception as e:
        print_error(f"Backup operation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    # ========================================================================
    # 8. Display results
    # ========================================================================
    if not args.quiet:
        display_results(results, start_time)
    else:
        # In quiet mode, only show errors
        failed = [r for r in results if not r['success']]
        if failed:
            for r in failed:
                print_error(f"{r['device_name']}: {r.get('error', 'Unknown error')}")

    # ========================================================================
    # 9. Exit with appropriate code
    # ========================================================================
    failed_count = sum(1 for r in results if not r['success'])

    if failed_count == 0:
        if not args.quiet:
            print_success("All backups completed successfully!")
        return 0
    else:
        if not args.quiet:
            print_error(f"{failed_count} backup(s) failed")
        return 1


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print()
        print_error("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
