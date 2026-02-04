#!/usr/bin/env python3
import argparse
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import from src module
from src.rollback import ConfigRollback
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

def list_device_backups_cli(
    rollback_mgr: ConfigRollback,
    device_name: str,
    limit: int = 10
) -> int:
    """
    List available backups for a device.

    Args:
        rollback_mgr: ConfigRollback instance
        device_name: Device name
        limit: Maximum number of backups to show

    Returns:
        Exit code (0 for success, 1 for no backups found)
    """
    print_info(f"Listing backups for device '{device_name}'...")
    print()

    backups = rollback_mgr.list_device_backups(device_name, limit=limit)

    if not backups:
        print_error(f"No backups found for device '{device_name}'")
        return 1

    print_success(f"Found {len(backups)} backup(s):")
    print()

    # Display table header
    print(f"{'#':<4} {'Filename':<40} {'Age':<20} {'Size':<10}")
    print("-" * 80)

    # Display backups
    for idx, backup in enumerate(backups, start=1):
        print(
            f"{idx:<4} {backup['filename']:<40} "
            f"{backup['age']:<20} {backup['size_readable']:<10}"
        )

    print()
    return 0


def preview_backup_cli(
    rollback_mgr: ConfigRollback,
    backup_filepath: str,
    lines: int = 50
) -> int:
    """
    Preview a backup file.

    Args:
        rollback_mgr: ConfigRollback instance
        backup_filepath: Path to backup file
        lines: Number of lines to preview

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        preview = rollback_mgr.preview_backup(backup_filepath, lines=lines)
        print(preview)
        return 0
    except Exception as e:
        print_error(f"Failed to preview backup: {e}")
        return 1


def get_devices_from_args(
    args: argparse.Namespace,
    inventory_loader: InventoryLoader
) -> List[Dict[str, Any]]:
    """
    Determine which devices to rollback based on CLI arguments.

    Args:
        args: Parsed command-line arguments
        inventory_loader: InventoryLoader instance

    Returns:
        List of devices to rollback

    Raises:
        SystemExit: If invalid device names are specified
    """
    devices = []

    # If specific devices requested
    if args.device:
        # Get each device by name
        for name in args.device:
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

    # All devices
    elif args.all:
        devices = inventory_loader.get_all_devices()

    return devices


def display_rollback_plan(
    devices: List[Dict[str, Any]],
    backup_strategy: str,
    safety_backup: bool,
    parallel: bool,
    dry_run: bool
) -> None:
    """
    Display rollback plan before execution.

    Args:
        devices: List of devices to rollback
        backup_strategy: Description of backup strategy (e.g., "latest", "specific file")
        safety_backup: Whether safety backup is enabled
        parallel: Whether parallel execution is enabled
        dry_run: Whether this is a dry-run
    """
    print_separator()
    print("ROLLBACK PLAN")
    print_separator()

    print(f"\nDevices to rollback: {len(devices)}")
    print(f"Backup strategy: {backup_strategy}")
    print(f"Safety backup: {'Enabled' if safety_backup else 'DISABLED'}")
    print(f"Execution mode: {'Parallel' if parallel else 'Sequential'}")
    if dry_run:
        print(f"Mode: DRY-RUN (preview only, no changes will be made)")
    print()

    # Display device table
    if devices:
        print("Device List:")
        print(format_device_list(devices))
    print()


def confirm_rollback(device_count: int, safety_backup: bool) -> bool:
    """
    Ask user to confirm rollback operation.

    Args:
        device_count: Number of devices to rollback
        safety_backup: Whether safety backup is enabled

    Returns:
        True if user confirms, False otherwise
    """
    if not safety_backup:
        print()
        print_error("WARNING: Safety backups are DISABLED!")
        print_error("No backup will be created before rollback.")
        print()

    try:
        response = input(f"\nProceed with rollback of {device_count} device(s)? [y/N]: ")
        return response.lower() in ['y', 'yes']
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def display_rollback_results(
    results: List[Dict[str, Any]],
    start_time: datetime,
    rollback_mgr: ConfigRollback
) -> int:
    """
    Display rollback results summary.

    Args:
        results: List of rollback result dictionaries
        start_time: Rollback start time
        rollback_mgr: ConfigRollback instance

    Returns:
        Exit code (0 for success, 1 for failures)
    """
    print()
    print_separator()
    print("ROLLBACK RESULTS")
    print_separator()
    print()

    # Calculate execution time
    execution_time = datetime.now() - start_time
    execution_seconds = execution_time.total_seconds()

    # Generate and display report
    report = rollback_mgr.generate_rollback_report(results)
    print(report)

    print(f"Execution time: {execution_seconds:.1f} seconds")
    print()
    print_separator()

    # Determine exit code
    failed_count = sum(1 for r in results if not r['success'])
    return 1 if failed_count > 0 else 0


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
        description="Network Device Configuration Rollback Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List available backups for a device
  %(prog)s --list spine1

  # Preview a specific backup
  %(prog)s --preview configs/backups/spine1_20250203_143022.cfg

  # Rollback device to latest backup
  %(prog)s --device spine1 --latest

  # Rollback device to specific backup
  %(prog)s --device spine1 --backup configs/backups/spine1_20250203_143022.cfg

  # Rollback multiple devices to latest backups
  %(prog)s --device spine1 --device spine2 --latest

  # Rollback all spine devices to latest (with safety backup)
  %(prog)s --role spine --latest

  # Dry-run rollback (preview only)
  %(prog)s --device leaf1 --latest --dry-run

  # Rollback without safety backup (not recommended!)
  %(prog)s --device spine1 --latest --no-safety-backup

  # Parallel rollback
  %(prog)s --role leaf --latest --parallel
        """
    )

    # Action arguments (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        '--list', '-l',
        metavar='DEVICE',
        help='List available backups for a device'
    )
    action_group.add_argument(
        '--preview', '-p',
        metavar='BACKUP_FILE',
        help='Preview a backup file'
    )

    # Device selection arguments (for rollback operations)
    device_group = parser.add_argument_group('Device Selection (for rollback)')
    device_group.add_argument(
        '--device', '-d',
        action='append',
        metavar='NAME',
        help='Rollback specific device(s) by name (can be specified multiple times)'
    )
    device_group.add_argument(
        '--role', '-r',
        metavar='ROLE',
        help='Rollback all devices with specific role (e.g., spine, leaf)'
    )
    device_group.add_argument(
        '--all', '-a',
        action='store_true',
        help='Rollback all devices in inventory'
    )

    # Backup selection arguments (for rollback operations)
    backup_group = parser.add_argument_group('Backup Selection (for rollback)')
    backup_select = backup_group.add_mutually_exclusive_group()
    backup_select.add_argument(
        '--latest',
        action='store_true',
        help='Use latest backup for each device'
    )
    backup_select.add_argument(
        '--backup', '-b',
        metavar='FILE',
        help='Rollback to specific backup file (only for single device)'
    )
    backup_select.add_argument(
        '--timestamp', '-t',
        metavar='DATETIME',
        help='Rollback to backup closest to timestamp (format: YYYY-MM-DD HH:MM:SS)'
    )

    # Execution options
    exec_group = parser.add_argument_group('Execution Options')
    exec_group.add_argument(
        '--parallel',
        action='store_true',
        default=False,
        help='Enable parallel execution (default: sequential)'
    )
    exec_group.add_argument(
        '--no-safety-backup',
        action='store_true',
        help='Skip safety backup before rollback (use with caution!)'
    )
    exec_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview rollback without applying (safe testing mode)'
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
    output_group.add_argument(
        '--lines',
        type=int,
        default=50,
        metavar='N',
        help='Number of lines to preview (default: 50)'
    )

    # Parse arguments
    args = parser.parse_args()

    # Validate mutually exclusive options
    if args.verbose and args.quiet:
        parser.error("--verbose and --quiet cannot be used together")

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
    # 3. Initialize ConfigRollback
    # ========================================================================
    try:
        if not args.quiet and not args.list and not args.preview:
            print_info("Initializing rollback system...")

        rollback_mgr = ConfigRollback(
            inventory_path="inventory/devices.yaml",
            backup_dir="configs/backups",
            create_safety_backup=not args.no_safety_backup
        )

        if not args.quiet and not args.list and not args.preview:
            print_success("Rollback system initialized")

    except FileNotFoundError as e:
        print_error(f"Inventory file not found: {e}")
        print_info("Make sure you're running from the project root directory")
        return 2

    except Exception as e:
        print_error(f"Failed to initialize rollback system: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2

    # ========================================================================
    # 4. Handle list action
    # ========================================================================
    if args.list:
        return list_device_backups_cli(rollback_mgr, args.list)

    # ========================================================================
    # 5. Handle preview action
    # ========================================================================
    if args.preview:
        return preview_backup_cli(rollback_mgr, args.preview, lines=args.lines)

    # ========================================================================
    # 6. Validate rollback arguments
    # ========================================================================
    if not (args.device or args.role or args.all):
        parser.error("For rollback operations, at least one device selection method is required (--device, --role, or --all)")

    if not (args.latest or args.backup or args.timestamp):
        parser.error("For rollback operations, backup selection is required (--latest, --backup, or --timestamp)")

    if args.backup and (args.device and len(args.device) > 1 or args.role or args.all):
        parser.error("--backup can only be used with a single device (use --device with one device name)")

    # ========================================================================
    # 7. Load inventory and determine which devices to rollback
    # ========================================================================
    try:
        if not args.quiet:
            print_info("Loading device inventory...")

        devices = get_devices_from_args(args, rollback_mgr.inventory_loader)

        if not devices:
            print_error("No devices found to rollback")
            return 2

        if not args.quiet:
            print_success(f"Loaded {len(devices)} device(s)")

    except SystemExit:
        raise

    except Exception as e:
        print_error(f"Failed to load devices: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2

    # ========================================================================
    # 8. Prepare backup selection strategy
    # ========================================================================
    backup_strategy = ""
    devices_and_backups = []

    try:
        if args.latest:
            backup_strategy = "Latest backup for each device"

            # Find latest backup for each device
            for device in devices:
                device_name = device.get('name', 'unknown')
                latest = rollback_mgr.get_latest_backup(device_name)

                if not latest:
                    print_error(f"No backups found for device '{device_name}'")
                    return 2

                devices_and_backups.append((device, latest['filepath']))

        elif args.backup:
            backup_strategy = f"Specific backup: {os.path.basename(args.backup)}"

            # Validate backup file exists
            valid, msg = rollback_mgr._validate_backup_file(args.backup)
            if not valid:
                print_error(f"Invalid backup file: {msg}")
                return 2

            devices_and_backups.append((devices[0], args.backup))

        elif args.timestamp:
            backup_strategy = f"Backup closest to: {args.timestamp}"

            # Parse timestamp
            try:
                target_dt = datetime.strptime(args.timestamp, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                print_error(f"Invalid timestamp format. Use: YYYY-MM-DD HH:MM:SS")
                return 2

            # Find closest backup for each device
            for device in devices:
                device_name = device.get('name', 'unknown')
                backups = rollback_mgr.list_device_backups(device_name, limit=0)

                if not backups:
                    print_error(f"No backups found for device '{device_name}'")
                    return 2

                # Find closest backup
                closest = None
                min_diff = None

                for backup in backups:
                    backup_dt = rollback_mgr._parse_timestamp_from_filename(backup['filename'])
                    if backup_dt:
                        diff = abs((backup_dt - target_dt).total_seconds())
                        if min_diff is None or diff < min_diff:
                            min_diff = diff
                            closest = backup

                if not closest:
                    print_error(f"No valid backup found for device '{device_name}'")
                    return 2

                devices_and_backups.append((device, closest['filepath']))

    except Exception as e:
        print_error(f"Failed to prepare rollback: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2

    # ========================================================================
    # 9. Display rollback plan
    # ========================================================================
    if not args.quiet:
        display_rollback_plan(
            devices,
            backup_strategy,
            not args.no_safety_backup,
            args.parallel,
            args.dry_run
        )

    # ========================================================================
    # 10. Confirm rollback (unless --yes or --dry-run)
    # ========================================================================
    if not args.yes and not args.dry_run and not args.quiet:
        if not confirm_rollback(len(devices), not args.no_safety_backup):
            print_info("Rollback cancelled by user")
            return 0

    # ========================================================================
    # 11. Execute rollback
    # ========================================================================
    try:
        if args.dry_run:
            # Dry-run mode: show what would happen
            if not args.quiet:
                print()
                print_info("DRY-RUN MODE: Showing rollback plan (no changes will be made)")
                print()

            # Create mock results
            results = []
            for device, backup_path in devices_and_backups:
                device_name = device.get('name', 'unknown')
                backup_file = os.path.basename(backup_path)

                # Validate backup
                valid, msg = rollback_mgr._validate_backup_file(backup_path)

                if valid:
                    print_success(f"{device_name:<15} would be rolled back to {backup_file}")
                    results.append({
                        'success': True,
                        'device_name': device_name,
                        'backup_file_used': backup_path,
                        'safety_backup_created': None,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'error': None
                    })
                else:
                    print_error(f"{device_name:<15} invalid backup: {msg}")
                    results.append({
                        'success': False,
                        'device_name': device_name,
                        'backup_file_used': backup_path,
                        'safety_backup_created': None,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'error': f"Invalid backup: {msg}"
                    })

            print()
            print_info("DRY-RUN COMPLETE: No changes were made to devices")
            return 0

        else:
            # Real rollback
            if not args.quiet:
                print()
                print_info(f"Starting rollback operation...")

            start_time = datetime.now()

            # Execute rollback
            if len(devices_and_backups) == 1:
                # Single device rollback
                device, backup_path = devices_and_backups[0]
                result = rollback_mgr.rollback_device(device, backup_path)
                results = [result]
            else:
                # Multiple devices rollback
                results = rollback_mgr.rollback_multiple_devices(
                    devices_and_backups,
                    parallel=args.parallel
                )

    except KeyboardInterrupt:
        print()
        print_error("Rollback interrupted by user")
        return 1

    except Exception as e:
        print_error(f"Rollback operation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    # ========================================================================
    # 12. Display results
    # ========================================================================
    if not args.quiet:
        exit_code = display_rollback_results(results, start_time, rollback_mgr)
    else:
        # In quiet mode, only show errors
        failed = [r for r in results if not r['success']]
        if failed:
            for r in failed:
                print_error(f"{r['device_name']}: {r.get('error', 'Unknown error')}")
            exit_code = 1
        else:
            exit_code = 0

    # ========================================================================
    # 13. Exit with appropriate code
    # ========================================================================
    failed_count = sum(1 for r in results if not r['success'])

    if failed_count == 0:
        if not args.quiet and not args.dry_run:
            print_success("All rollbacks completed successfully!")
        return exit_code
    else:
        if not args.quiet:
            print_error(f"{failed_count} rollback(s) failed")
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
