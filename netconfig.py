#!/usr/bin/env python3
import argparse
import sys
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv not installed, skip auto-loading
    pass

# Add project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import from src module
from src.backup import ConfigBackup
from src.deployment import ConfigDeployment
from src.rollback import ConfigRollback
from src.inventory_loader import InventoryLoader
from src.template_engine import TemplateEngine
from src.utils import (
    setup_logging,
    get_logger,
    print_info,
    print_success,
    print_error,
    print_separator,
    format_device_list,
    safe_write_file,
    safe_read_file,
    get_human_timestamp,
)

# Version
VERSION = "1.0.0"


# ============================================================================
# PARSER SETUP FUNCTIONS
# ============================================================================

def setup_backup_parser(subparsers) -> argparse.ArgumentParser:
    """
    Configure the backup subcommand parser.

    Args:
        subparsers: The subparsers object to add this parser to

    Returns:
        The configured backup parser
    """
    backup_parser = subparsers.add_parser(
        'backup',
        help='Backup device configurations',
        description='Backup network device configurations to local files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  netconfig backup --all
      Backup all devices in parallel

  netconfig backup --device spine1 --device leaf1
      Backup specific devices

  netconfig backup --role spine --no-parallel
      Backup all spine devices sequentially

  netconfig backup --all --backup-dir /tmp/backups
      Backup to custom directory
        """
    )

    # Device selection
    device_group = backup_parser.add_argument_group('device selection')
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
        help='Backup all devices in inventory'
    )

    # Backup options
    backup_group = backup_parser.add_argument_group('backup options')
    backup_group.add_argument(
        '--backup-dir',
        metavar='PATH',
        default='configs/backups',
        help='Custom backup directory path (default: configs/backups)'
    )
    backup_group.add_argument(
        '--parallel',
        action='store_true',
        default=True,
        dest='parallel',
        help='Enable parallel execution (default)'
    )
    backup_group.add_argument(
        '--no-parallel',
        action='store_false',
        dest='parallel',
        help='Disable parallel execution (sequential mode)'
    )
    backup_group.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )

    return backup_parser


def setup_deploy_parser(subparsers) -> argparse.ArgumentParser:
    """
    Configure the deploy subcommand parser.

    Args:
        subparsers: The subparsers object to add this parser to

    Returns:
        The configured deploy parser
    """
    deploy_parser = subparsers.add_parser(
        'deploy',
        help='Deploy configurations from templates',
        description='Deploy network configurations using Jinja2 templates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  netconfig deploy -t ntp_config.j2 --all --vars '{"ntp_server": "10.0.0.1"}'
      Deploy NTP configuration to all devices

  netconfig deploy -t ntp_config.j2 --device spine1 --vars @vars.json --dry-run
      Preview deployment with variables from file

  netconfig deploy -t snmp_config.j2 --role spine --vars '{"community": "public"}' --yes
      Deploy SNMP configuration to spine devices without confirmation
        """
    )

    # Required arguments
    required_group = deploy_parser.add_argument_group('required arguments')
    required_group.add_argument(
        '--template', '-t',
        required=True,
        help='Template file name to use (e.g., ntp_config.j2)'
    )

    # Device selection
    device_group = deploy_parser.add_argument_group('device selection')
    device_group.add_argument(
        '--device', '-d',
        action='append',
        dest='devices',
        help='Deploy to specific device(s) by name (can be repeated)'
    )
    device_group.add_argument(
        '--role', '-r',
        help='Deploy to all devices with specific role (e.g., spine, leaf)'
    )
    device_group.add_argument(
        '--all', '-a',
        action='store_true',
        help='Deploy to all devices in inventory'
    )

    # Deployment options
    deploy_group = deploy_parser.add_argument_group('deployment options')
    deploy_group.add_argument(
        '--variables', '--vars',
        help='JSON string or file path (prefix with @) containing template variables'
    )
    deploy_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview deployment without applying (safe testing mode)'
    )
    deploy_group.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip automatic pre-deployment backup (use with caution!)'
    )
    deploy_group.add_argument(
        '--parallel',
        action='store_true',
        help='Enable parallel deployment (default: sequential)'
    )
    deploy_group.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )

    return deploy_parser


def setup_rollback_parser(subparsers) -> argparse.ArgumentParser:
    """
    Configure the rollback subcommand parser.

    Args:
        subparsers: The subparsers object to add this parser to

    Returns:
        The configured rollback parser
    """
    rollback_parser = subparsers.add_parser(
        'rollback',
        help='Rollback to previous configurations',
        description='Restore network devices to previous configuration backups',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  netconfig rollback --device spine1 --latest
      Rollback device to latest backup

  netconfig rollback --device spine1 --backup configs/backups/spine1_20250203_143022.cfg
      Rollback to specific backup file

  netconfig rollback --role spine --latest --dry-run
      Preview rollback without applying changes
        """
    )

    # Device selection
    device_group = rollback_parser.add_argument_group('device selection')
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

    # Backup selection
    backup_group = rollback_parser.add_argument_group('backup selection')
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
    exec_group = rollback_parser.add_argument_group('execution options')
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

    return rollback_parser


def setup_list_parser(subparsers) -> argparse.ArgumentParser:
    """
    Configure the list subcommand parser.

    Args:
        subparsers: The subparsers object to add this parser to

    Returns:
        The configured list parser
    """
    list_parser = subparsers.add_parser(
        'list',
        help='List devices, backups, or templates',
        description='List and display information about devices, backups, and templates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  netconfig list --devices
      List all devices in inventory

  netconfig list --backups spine1
      List backups for device

  netconfig list --templates
      List available templates

  netconfig list --devices --format json
      List devices in JSON format
        """
    )

    # What to list
    list_group = list_parser.add_argument_group('list options')
    list_what = list_group.add_mutually_exclusive_group(required=True)
    list_what.add_argument(
        '--devices',
        action='store_true',
        help='List all devices in inventory'
    )
    list_what.add_argument(
        '--backups',
        metavar='DEVICE',
        help='List backups for specific device'
    )
    list_what.add_argument(
        '--templates',
        action='store_true',
        help='List available templates'
    )

    # Output format
    list_parser.add_argument(
        '--format',
        choices=['table', 'json', 'simple'],
        default='table',
        help='Output format (default: table)'
    )

    return list_parser


def setup_validate_parser(subparsers) -> argparse.ArgumentParser:
    """
    Configure the validate subcommand parser.

    Args:
        subparsers: The subparsers object to add this parser to

    Returns:
        The configured validate parser
    """
    validate_parser = subparsers.add_parser(
        'validate',
        help='Validate inventory, templates, or backups',
        description='Validate configuration files, templates, and backups',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  netconfig validate --inventory
      Validate inventory file structure

  netconfig validate --template ntp_config.j2
      Validate specific template syntax

  netconfig validate --templates
      Validate all templates

  netconfig validate --backup configs/backups/spine1_20250203_143022.cfg
      Validate backup file
        """
    )

    # What to validate
    validate_group = validate_parser.add_argument_group('validation options')
    validate_what = validate_group.add_mutually_exclusive_group(required=True)
    validate_what.add_argument(
        '--inventory',
        action='store_true',
        help='Validate inventory file structure'
    )
    validate_what.add_argument(
        '--template',
        metavar='NAME',
        help='Validate specific template'
    )
    validate_what.add_argument(
        '--templates',
        action='store_true',
        help='Validate all templates'
    )
    validate_what.add_argument(
        '--backup',
        metavar='FILE',
        help='Validate backup file'
    )

    return validate_parser


# ============================================================================
# COMMAND HANDLER FUNCTIONS
# ============================================================================

def handle_backup(args: argparse.Namespace) -> int:
    """
    Handle the backup command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failures, 2 for errors)
    """
    logger = get_logger(__name__)

    # Initialize backup manager
    try:
        if not args.quiet:
            print_info("Initializing backup system...")

        backup_mgr = ConfigBackup(
            inventory_path=args.config,
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

    # Determine which devices to backup
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
        raise

    except Exception as e:
        print_error(f"Failed to load devices: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2

    # Display backup plan
    if not args.quiet:
        display_backup_plan(devices, args.parallel, args.backup_dir)

    # Confirm if multiple devices
    if not args.yes and len(devices) > 1 and not args.quiet:
        if not confirm_operation(
            f"Proceed with backup of {len(devices)} device(s)?",
            default_yes=True
        ):
            print_info("Backup cancelled by user")
            return 0

    # Execute backup
    try:
        if not args.quiet:
            print_info("Starting backup operation...")

        start_time = datetime.now()

        if len(devices) == 1:
            result = backup_mgr.backup_device(devices[0])
            results = [result]
        else:
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

    # Display results
    if not args.quiet:
        display_backup_results(results, start_time)
    else:
        # In quiet mode, only show errors
        failed = [r for r in results if not r['success']]
        if failed:
            for r in failed:
                print_error(f"{r['device_name']}: {r.get('error', 'Unknown error')}")

    # Exit with appropriate code
    failed_count = sum(1 for r in results if not r['success'])

    if failed_count == 0:
        if not args.quiet:
            print_success("All backups completed successfully!")
        return 0
    else:
        if not args.quiet:
            print_error(f"{failed_count} backup(s) failed")
        return 1


def handle_deploy(args: argparse.Namespace) -> int:
    """
    Handle the deploy command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failures, 2 for errors)
    """
    logger = get_logger(__name__)

    # Initialize components
    try:
        if not args.quiet:
            print_info("Initializing deployment system...")

        inventory_loader = InventoryLoader(args.config)
        template_engine = TemplateEngine()

        auto_backup = not args.no_backup
        deployer = ConfigDeployment(auto_backup=auto_backup)

        if not args.quiet:
            print_success("Deployment system initialized")

    except FileNotFoundError as e:
        print_error(str(e))
        return 2

    except Exception as e:
        logger.exception("Failed to initialize deployment system")
        print_error(f"Initialization failed: {e}")
        return 2

    # Validate template exists
    templates = template_engine.list_templates()
    template_name_with_ext = args.template if args.template.endswith('.j2') else f"{args.template}.j2"

    if template_name_with_ext not in templates:
        print_error(f"Template not found: {args.template}")
        print()
        print("Available templates:")
        if templates:
            for template in templates:
                print(f"  - {template}")
        else:
            print("  (no templates available)")
        return 2

    # Load variables
    try:
        variables = load_variables(args.variables)
        logger.debug(f"Loaded {len(variables)} variables")

    except ValueError as e:
        print_error(f"Invalid variables: {e}")
        return 2

    except FileNotFoundError as e:
        print_error(str(e))
        return 2

    except Exception as e:
        logger.exception("Failed to load variables")
        print_error(f"Failed to load variables: {e}")
        return 2

    # Get target devices
    try:
        target_devices = get_devices_from_args(args, inventory_loader)

        if not target_devices:
            print_error("No target devices selected")
            return 2

        logger.info(f"Selected {len(target_devices)} target device(s)")

    except Exception as e:
        logger.exception("Failed to load target devices")
        print_error(f"Failed to load devices: {e}")
        return 2

    # Display deployment plan
    if not args.quiet:
        display_deployment_plan(
            devices=target_devices,
            template_name=args.template,
            variables=variables,
            dry_run=args.dry_run,
            backup_enabled=auto_backup,
            parallel=args.parallel
        )

    # Show warning if no backup
    if args.no_backup and not args.dry_run and not args.quiet:
        print()
        print_error("WARNING: Automatic backups are DISABLED!")
        print_error("Proceeding without backups is risky and not recommended.")
        print()

    # Confirm deployment
    if not args.dry_run and not args.quiet and not args.yes:
        if not confirm_operation(
            f"Continue with deployment to {len(target_devices)} device(s)?",
            default_yes=False
        ):
            print()
            print_info("Deployment cancelled by user")
            return 0

    # Execute deployment
    try:
        start_time = datetime.now()

        if args.dry_run:
            # Dry-run mode: show previews
            if not args.quiet:
                print()
                print_info("DRY-RUN MODE: Generating configuration previews...")

            preview_deployments(deployer, target_devices, args.template, variables)

            # Create mock results
            results = []
            for device in target_devices:
                results.append({
                    'success': True,
                    'device_name': device.get('name', 'unknown'),
                    'template_used': args.template,
                    'backup_created': None,
                    'dry_run': True,
                    'config_preview': '(preview generated)',
                    'error': None,
                    'timestamp': get_human_timestamp(),
                    'output': None
                })
        else:
            # Real deployment
            if not args.quiet:
                print()
                print_info(f"Starting deployment to {len(target_devices)} device(s)...")
                print()

            results = deployer.deploy_to_multiple_devices(
                devices=target_devices,
                template_name=args.template,
                variables_list=variables,
                dry_run=False,
                parallel=args.parallel,
                max_workers=5
            )

    except KeyboardInterrupt:
        print()
        print_error("Deployment interrupted by user")
        logger.warning("Deployment interrupted by user (Ctrl+C)")
        return 1

    except Exception as e:
        logger.exception("Deployment failed")
        print_error(f"Deployment failed: {e}")
        return 1

    # Display results
    if not args.quiet:
        exit_code = display_deployment_results(results, start_time, deployer)
    else:
        # In quiet mode, only show errors
        failed = [r for r in results if not r['success']]
        if failed:
            for result in failed:
                print_error(f"{result['device_name']}: {result['error']}")
            exit_code = 1
        else:
            exit_code = 0

    return exit_code


def handle_rollback(args: argparse.Namespace) -> int:
    """
    Handle the rollback command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for failures, 2 for errors)
    """
    logger = get_logger(__name__)

    # Initialize rollback manager
    try:
        if not args.quiet:
            print_info("Initializing rollback system...")

        rollback_mgr = ConfigRollback(
            inventory_path=args.config,
            backup_dir="configs/backups",
            create_safety_backup=not args.no_safety_backup
        )

        if not args.quiet:
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

    # Validate rollback arguments
    if not (args.device or args.role or args.all):
        print_error("Device selection is required (--device, --role, or --all)")
        return 2

    if not (args.latest or args.backup or args.timestamp):
        print_error("Backup selection is required (--latest, --backup, or --timestamp)")
        return 2

    if args.backup and (args.device and len(args.device) > 1 or args.role or args.all):
        print_error("--backup can only be used with a single device")
        return 2

    # Load devices
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

    # Prepare backup selection strategy
    backup_strategy = ""
    devices_and_backups = []

    try:
        if args.latest:
            backup_strategy = "Latest backup for each device"

            for device in devices:
                device_name = device.get('name', 'unknown')
                latest = rollback_mgr.get_latest_backup(device_name)

                if not latest:
                    print_error(f"No backups found for device '{device_name}'")
                    return 2

                devices_and_backups.append((device, latest['filepath']))

        elif args.backup:
            backup_strategy = f"Specific backup: {os.path.basename(args.backup)}"

            valid, msg = rollback_mgr._validate_backup_file(args.backup)
            if not valid:
                print_error(f"Invalid backup file: {msg}")
                return 2

            devices_and_backups.append((devices[0], args.backup))

        elif args.timestamp:
            backup_strategy = f"Backup closest to: {args.timestamp}"

            try:
                target_dt = datetime.strptime(args.timestamp, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                print_error("Invalid timestamp format. Use: YYYY-MM-DD HH:MM:SS")
                return 2

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

    # Display rollback plan
    if not args.quiet:
        display_rollback_plan(
            devices,
            backup_strategy,
            not args.no_safety_backup,
            args.parallel,
            args.dry_run
        )

    # Confirm rollback
    if not args.yes and not args.dry_run and not args.quiet:
        if not args.no_safety_backup:
            warning = f"Proceed with rollback of {len(devices)} device(s)?"
        else:
            print()
            print_error("WARNING: Safety backups are DISABLED!")
            print_error("No backup will be created before rollback.")
            print()
            warning = f"Proceed with rollback of {len(devices)} device(s) WITHOUT safety backup?"

        if not confirm_operation(warning, default_yes=False):
            print_info("Rollback cancelled by user")
            return 0

    # Execute rollback
    try:
        if args.dry_run:
            # Dry-run mode
            if not args.quiet:
                print()
                print_info("DRY-RUN MODE: Showing rollback plan (no changes will be made)")
                print()

            results = []
            for device, backup_path in devices_and_backups:
                device_name = device.get('name', 'unknown')
                backup_file = os.path.basename(backup_path)

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
                print_info("Starting rollback operation...")

            start_time = datetime.now()

            if len(devices_and_backups) == 1:
                device, backup_path = devices_and_backups[0]
                result = rollback_mgr.rollback_device(device, backup_path)
                results = [result]
            else:
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

    # Display results
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

    failed_count = sum(1 for r in results if not r['success'])

    if failed_count == 0:
        if not args.quiet and not args.dry_run:
            print_success("All rollbacks completed successfully!")
        return exit_code
    else:
        if not args.quiet:
            print_error(f"{failed_count} rollback(s) failed")
        return 1


def handle_list(args: argparse.Namespace) -> int:
    """
    Handle the list command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    logger = get_logger(__name__)

    try:
        if args.devices:
            # List devices
            inventory_loader = InventoryLoader(args.config)
            devices = inventory_loader.get_all_devices()

            if not devices:
                print_info("No devices found in inventory")
                return 0

            if args.format == 'json':
                print(json.dumps(devices, indent=2))

            elif args.format == 'simple':
                for device in devices:
                    print(device.get('name', 'unknown'))

            else:  # table format
                print_info(f"Found {len(devices)} device(s) in inventory:\n")
                print(format_device_list(devices))

        elif args.backups:
            # List backups for device
            rollback_mgr = ConfigRollback(inventory_path=args.config)
            backups = rollback_mgr.list_device_backups(args.backups, limit=20)

            if not backups:
                print_info(f"No backups found for device '{args.backups}'")
                return 0

            if args.format == 'json':
                print(json.dumps(backups, indent=2))

            elif args.format == 'simple':
                for backup in backups:
                    print(backup['filename'])

            else:  # table format
                print_info(f"Found {len(backups)} backup(s) for device '{args.backups}':\n")
                print(f"{'#':<4} {'Filename':<40} {'Age':<20} {'Size':<10}")
                print("-" * 80)

                for idx, backup in enumerate(backups, start=1):
                    print(
                        f"{idx:<4} {backup['filename']:<40} "
                        f"{backup['age']:<20} {backup['size_readable']:<10}"
                    )
                print()

        elif args.templates:
            # List templates
            template_engine = TemplateEngine()
            templates = template_engine.list_templates()

            if not templates:
                print_info("No templates found")
                return 0

            if args.format == 'json':
                template_info = []
                for template in templates:
                    template_path = os.path.join(template_engine.template_dir, template)
                    size = os.path.getsize(template_path)
                    template_info.append({
                        'name': template,
                        'path': template_path,
                        'size': size
                    })
                print(json.dumps(template_info, indent=2))

            elif args.format == 'simple':
                for template in templates:
                    print(template)

            else:  # table format
                print_info(f"Found {len(templates)} template(s):\n")
                print(f"{'Template Name':<40} {'Size':<10}")
                print("-" * 50)

                for template in templates:
                    template_path = os.path.join(template_engine.template_dir, template)
                    size = os.path.getsize(template_path)
                    size_kb = size / 1024
                    print(f"{template:<40} {size_kb:.1f} KB")
                print()

        return 0

    except Exception as e:
        logger.exception("List operation failed")
        print_error(f"List operation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def handle_validate(args: argparse.Namespace) -> int:
    """
    Handle the validate command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for validation errors)
    """
    logger = get_logger(__name__)

    try:
        if args.inventory:
            # Validate inventory
            print_info("Validating inventory file...")

            try:
                inventory_loader = InventoryLoader(args.config)
                devices = inventory_loader.get_all_devices()

                if not devices:
                    print_error("Inventory is empty")
                    return 1

                print_success(f"Inventory file is valid ({len(devices)} devices)")

                # Additional checks
                errors = []

                for device in devices:
                    name = device.get('name', 'unknown')

                    if not device.get('ip'):
                        errors.append(f"Device '{name}' missing IP address")

                    if not device.get('device_type'):
                        errors.append(f"Device '{name}' missing device_type")

                if errors:
                    print()
                    print_error("Validation warnings:")
                    for error in errors:
                        print(f"  - {error}")
                    return 1
                else:
                    print_success("All devices have required fields")
                    return 0

            except Exception as e:
                print_error(f"Inventory validation failed: {e}")
                return 1

        elif args.template:
            # Validate specific template
            print_info(f"Validating template '{args.template}'...")

            template_engine = TemplateEngine()
            is_valid, message = template_engine.validate_template(args.template)

            if is_valid:
                print_success(f"Template '{args.template}' is valid")

                # Show variables
                try:
                    variables = template_engine.get_template_variables(args.template)
                    if variables:
                        print()
                        print_info("Template variables:")
                        for var in sorted(variables):
                            print(f"  - {var}")
                except Exception:
                    pass

                return 0
            else:
                print_error(f"Template '{args.template}' validation failed:")
                print(f"  {message}")
                return 1

        elif args.templates:
            # Validate all templates
            print_info("Validating all templates...\n")

            template_engine = TemplateEngine()
            templates = template_engine.list_templates()

            if not templates:
                print_info("No templates found")
                return 0

            valid_count = 0
            invalid_count = 0

            for template in templates:
                is_valid, message = template_engine.validate_template(template)

                if is_valid:
                    print_success(f"{template:<40} Valid")
                    valid_count += 1
                else:
                    print_error(f"{template:<40} {message}")
                    invalid_count += 1

            print()
            print_separator()
            print(f"Valid:   {valid_count}")
            print(f"Invalid: {invalid_count}")
            print_separator()

            return 0 if invalid_count == 0 else 1

        elif args.backup:
            # Validate backup file
            print_info(f"Validating backup file '{args.backup}'...")

            if not os.path.exists(args.backup):
                print_error("Backup file does not exist")
                return 1

            if not os.path.isfile(args.backup):
                print_error("Path is not a file")
                return 1

            # Check if readable
            try:
                content = safe_read_file(args.backup)
                if not content:
                    print_error("Backup file is empty")
                    return 1

                size = os.path.getsize(args.backup)
                lines = len(content.splitlines())

                print_success("Backup file is valid")
                print()
                print(f"  Size:  {size / 1024:.1f} KB")
                print(f"  Lines: {lines}")

                return 0

            except Exception as e:
                print_error(f"Failed to read backup file: {e}")
                return 1

    except Exception as e:
        logger.exception("Validate operation failed")
        print_error(f"Validate operation failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_devices_from_args(
    args: argparse.Namespace,
    inventory_loader: InventoryLoader
) -> List[Dict[str, Any]]:
    """
    Determine which devices to operate on based on CLI arguments.

    Args:
        args: Parsed command-line arguments
        inventory_loader: InventoryLoader instance

    Returns:
        List of devices to operate on

    Raises:
        SystemExit: If invalid device names are specified
    """
    devices = []

    # Check for device argument (handle both 'device' and 'devices')
    device_arg = getattr(args, 'device', None) or getattr(args, 'devices', None)

    if device_arg:
        # Get each device by name
        for name in device_arg:
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

    elif getattr(args, 'all', False):
        devices = inventory_loader.get_all_devices()

    # Remove duplicates
    seen = set()
    unique_devices = []
    for device in devices:
        device_name = device.get('name')
        if device_name not in seen:
            seen.add(device_name)
            unique_devices.append(device)

    return unique_devices


def load_variables(vars_arg: Optional[str]) -> Dict[str, Any]:
    """
    Load variables from JSON string or file.

    Args:
        vars_arg: JSON string or file path (prefixed with @)

    Returns:
        Dictionary of variables

    Raises:
        ValueError: If JSON is invalid or file not found
    """
    if not vars_arg:
        return {}

    logger = get_logger(__name__)

    try:
        # Check if loading from file (starts with @)
        if vars_arg.startswith('@'):
            filepath = vars_arg[1:]  # Remove @ prefix
            logger.debug(f"Loading variables from file: {filepath}")

            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Variables file not found: {filepath}")

            with open(filepath, 'r', encoding='utf-8') as f:
                variables = json.load(f)

            logger.info(f"Loaded {len(variables)} variables from {filepath}")
            return variables

        else:
            # Parse as JSON string
            logger.debug("Parsing variables from JSON string")
            variables = json.loads(vars_arg)
            logger.info(f"Parsed {len(variables)} variables from JSON string")
            return variables

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to load variables: {e}")


def confirm_operation(message: str, default_yes: bool = False) -> bool:
    """
    Ask user to confirm operation.

    Args:
        message: Confirmation message
        default_yes: Whether default is yes

    Returns:
        True if user confirms, False otherwise
    """
    prompt = f"\n{message} [{'Y/n' if default_yes else 'y/N'}]: "

    try:
        response = input(prompt).strip().lower()

        if not response:
            return default_yes

        return response in ['y', 'yes']

    except (EOFError, KeyboardInterrupt):
        print()
        return False


def display_backup_plan(
    devices: List[Dict[str, Any]],
    parallel: bool,
    backup_dir: str
) -> None:
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

    if devices:
        print("Device List:")
        print(format_device_list(devices))
    print()


def display_backup_results(results: List[Dict[str, Any]], start_time: datetime) -> None:
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
            if len(error) > 60:
                error = error[:57] + "..."
            print_error(f"{r['device_name']:<15} -> {error}")
        print()

    print_separator()


def display_deployment_plan(
    devices: List[Dict[str, Any]],
    template_name: str,
    variables: Dict[str, Any],
    dry_run: bool,
    backup_enabled: bool,
    parallel: bool
) -> None:
    """
    Display deployment plan before execution.

    Args:
        devices: List of device dictionaries
        template_name: Template file name
        variables: Variables dictionary
        dry_run: Whether this is a dry-run
        backup_enabled: Whether backups are enabled
        parallel: Whether parallel deployment is enabled
    """
    print()
    print_separator("=", 80)
    print("DEPLOYMENT PLAN")
    print_separator("=", 80)

    print(f"\nTemplate:         {template_name}")

    if variables:
        print(f"\nVariables:")
        for key, value in variables.items():
            # Hide sensitive values
            if any(secret in key.lower() for secret in ['password', 'secret', 'key']):
                value = '***HIDDEN***'
            print(f"  {key:<20} = {value}")
    else:
        print(f"\nVariables:        None")

    print(f"\nTarget Devices:   {len(devices)}")
    print()
    print(format_device_list(devices))

    print()
    print_separator("-", 80)
    print("EXECUTION MODE")
    print_separator("-", 80)
    print(f"Mode:             {'DRY-RUN (preview only)' if dry_run else 'LIVE DEPLOYMENT'}")
    print(f"Backup:           {'Enabled' if backup_enabled else 'DISABLED'}")
    print(f"Parallel:         {'Yes' if parallel else 'No (sequential)'}")
    print_separator("=", 80)
    print()


def preview_deployments(
    deployer: ConfigDeployment,
    devices: List[Dict[str, Any]],
    template_name: str,
    variables: Dict[str, Any]
) -> None:
    """
    Show deployment previews for all devices.

    Args:
        deployer: ConfigDeployment instance
        devices: List of device dictionaries
        template_name: Template file name
        variables: Variables dictionary
    """
    logger = get_logger(__name__)

    print()
    print_info(f"Generating previews for {len(devices)} device(s)...")
    print()

    for idx, device in enumerate(devices, start=1):
        device_name = device.get('name', device.get('ip', 'unknown'))

        try:
            print_separator("=", 80)
            print(f"PREVIEW {idx}/{len(devices)} - Device: {device_name}")
            print_separator("=", 80)

            preview = deployer.preview_deployment(device, template_name, variables)
            print(preview)

        except Exception as e:
            logger.error(f"Failed to generate preview for {device_name}: {e}")
            print_error(f"Failed to generate preview for {device_name}: {e}")

        print()


def display_deployment_results(
    results: List[Dict[str, Any]],
    start_time: datetime,
    deployer: ConfigDeployment
) -> int:
    """
    Display deployment results.

    Args:
        results: List of deployment result dictionaries
        start_time: Deployment start time
        deployer: ConfigDeployment instance

    Returns:
        Exit code (0 for success, 1 for failures)
    """
    execution_time = datetime.now() - start_time
    execution_seconds = execution_time.total_seconds()

    report = deployer.generate_deployment_report(results)
    report += f"\nExecution Time:   {execution_seconds:.2f} seconds"
    report += "\n" + "=" * 80 + "\n"

    print()
    print(report)

    failed_count = sum(1 for r in results if not r['success'])
    return 1 if failed_count > 0 else 0


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
        backup_strategy: Description of backup strategy
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
        print("Mode: DRY-RUN (preview only, no changes will be made)")
    print()

    if devices:
        print("Device List:")
        print(format_device_list(devices))
    print()


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

    execution_time = datetime.now() - start_time
    execution_seconds = execution_time.total_seconds()

    report = rollback_mgr.generate_rollback_report(results)
    print(report)

    print(f"Execution time: {execution_seconds:.1f} seconds")
    print()
    print_separator()

    failed_count = sum(1 for r in results if not r['success'])
    return 1 if failed_count > 0 else 0


def setup_logging_for_cli(args: argparse.Namespace) -> None:
    """
    Setup logging based on global flags.

    Args:
        args: Parsed command-line arguments
    """
    if args.verbose:
        log_level = "DEBUG"
    elif args.quiet:
        log_level = "ERROR"
    else:
        log_level = "INFO"

    try:
        setup_logging(log_level=log_level)
    except Exception as e:
        print(f"Warning: Failed to setup logging: {e}", file=sys.stderr)


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0=success, 1=error, 130=cancelled)
    """
    # Create main parser
    parser = argparse.ArgumentParser(
        prog='netconfig',
        description='Network Configuration Management Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  netconfig backup --all
  netconfig deploy --template ntp.j2 --all --vars '{"server": "10.0.0.1"}'
  netconfig rollback --device spine1 --latest
  netconfig list --devices
  netconfig validate --inventory

For detailed help on each command:
  netconfig backup --help
  netconfig deploy --help
  netconfig rollback --help
  netconfig list --help
  netconfig validate --help

Shell Completion:
  For bash completion, add to ~/.bashrc:
    eval "$(register-python-argcomplete netconfig)"
        """
    )

    # Add global options
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output (show detailed progress and debug info)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output (only show errors)'
    )
    parser.add_argument(
        '--config',
        default='inventory/devices.yaml',
        help='Path to inventory file (default: inventory/devices.yaml)'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'NetConfig {VERSION}'
    )

    # Create subparsers
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        metavar='<command>'
    )

    # Add subcommands
    setup_backup_parser(subparsers)
    setup_deploy_parser(subparsers)
    setup_rollback_parser(subparsers)
    setup_list_parser(subparsers)
    setup_validate_parser(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # Show help if no command specified
    if not args.command:
        parser.print_help()
        return 1

    # Validate mutually exclusive global options
    if args.verbose and args.quiet:
        parser.error("--verbose and --quiet cannot be used together")

    # Setup logging based on global flags
    setup_logging_for_cli(args)

    # Route to appropriate handler
    try:
        if args.command == 'backup':
            return handle_backup(args)
        elif args.command == 'deploy':
            return handle_deploy(args)
        elif args.command == 'rollback':
            return handle_rollback(args)
        elif args.command == 'list':
            return handle_list(args)
        elif args.command == 'validate':
            return handle_validate(args)

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        return 130

    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Unexpected error: {e}")
        print_error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    return 0


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
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
