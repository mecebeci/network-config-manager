#!/usr/bin/env python3
import argparse
import sys
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import project modules
from src.deployment import ConfigDeployment
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
    get_human_timestamp,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_variables(vars_arg: Optional[str]) -> Dict[str, Any]:
    """
    Load variables from JSON string or file.

    Args:
        vars_arg: JSON string or file path (prefixed with @)

    Returns:
        Dictionary of variables

    Raises:
        ValueError: If JSON is invalid or file not found

    Example:
        # From JSON string
        vars = load_variables('{"ntp_server": "10.0.0.1"}')

        # From file
        vars = load_variables('@variables.json')
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

    # Template information
    print(f"\nTemplate:         {template_name}")

    # Variables information
    if variables:
        print(f"\nVariables:")
        for key, value in variables.items():
            # Hide sensitive values
            if any(secret in key.lower() for secret in ['password', 'secret', 'key']):
                value = '***HIDDEN***'
            print(f"  {key:<20} = {value}")
    else:
        print(f"\nVariables:        None")

    # Target devices
    print(f"\nTarget Devices:   {len(devices)}")
    print()
    print(format_device_list(devices))

    # Execution mode
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


def display_results(
    results: List[Dict[str, Any]],
    start_time: datetime,
    deployer: ConfigDeployment,
    output_file: Optional[str] = None
) -> int:
    """
    Display and optionally save deployment results.

    Args:
        results: List of deployment result dictionaries
        start_time: Deployment start time
        deployer: ConfigDeployment instance
        output_file: Optional file path to save report

    Returns:
        Exit code (0 for success, 1 for failures)
    """
    logger = get_logger(__name__)

    # Calculate execution time
    execution_time = datetime.now() - start_time
    execution_seconds = execution_time.total_seconds()

    # Generate report
    report = deployer.generate_deployment_report(results)

    # Add execution time to report
    report += f"\nExecution Time:   {execution_seconds:.2f} seconds"
    report += "\n" + "=" * 80 + "\n"

    # Display report to console
    print()
    print(report)

    # Save report to file if requested
    if output_file:
        try:
            if safe_write_file(output_file, report):
                print_success(f"Report saved to: {output_file}")
            else:
                print_error(f"Failed to save report to: {output_file}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            print_error(f"Failed to save report: {e}")

    # Determine exit code
    failed_count = sum(1 for r in results if not r['success'])
    return 1 if failed_count > 0 else 0


def confirm_deployment() -> bool:
    """
    Ask user to confirm deployment.

    Returns:
        True if user confirms, False otherwise
    """
    try:
        response = input("\nContinue with deployment? (y/n): ").strip().lower()
        return response in ['y', 'yes']
    except (KeyboardInterrupt, EOFError):
        print()
        return False


def validate_template_exists(template_engine: TemplateEngine, template_name: str) -> bool:
    """
    Validate that template exists.

    Args:
        template_engine: TemplateEngine instance
        template_name: Template name to validate

    Returns:
        True if template exists, False otherwise
    """
    templates = template_engine.list_templates()

    # Add .j2 extension if not present for comparison
    if not template_name.endswith('.j2'):
        template_name_with_ext = f"{template_name}.j2"
    else:
        template_name_with_ext = template_name

    if template_name_with_ext not in templates:
        print_error(f"Template not found: {template_name}")
        print()
        print("Available templates:")
        if templates:
            for template in templates:
                print(f"  - {template}")
        else:
            print("  (no templates available)")
        return False

    return True


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0=success, 1=failure, 2=error)
    """
    # ========================================================================
    # 1. PARSE ARGUMENTS
    # ========================================================================

    parser = argparse.ArgumentParser(
        description="Network Device Configuration Deployment Tool",
        epilog="""
Examples:
  # Preview deployment (dry-run)
  %(prog)s -t ntp_config.j2 -d spine1 --vars '{"ntp_server": "10.0.0.1"}' --dry-run

  # Deploy to specific device
  %(prog)s -t ntp_config.j2 -d spine1 --vars '{"ntp_server": "10.0.0.1"}'

  # Deploy to all spine devices
  %(prog)s -t snmp_config.j2 -r spine --vars '{"snmp_community": "public"}'

  # Deploy to all devices with variables from file
  %(prog)s -t ntp_config.j2 --all --vars @vars.json

  # Deploy without backup (not recommended)
  %(prog)s -t interface_config.j2 -d leaf1 --vars '{"interface": "ethernet-1/1"}' --no-backup

  # Parallel deployment with output file
  %(prog)s -t ntp_config.j2 --all --vars '{"ntp_server": "10.0.0.1"}' --parallel -o report.txt

  # Verbose mode
  %(prog)s -t ntp_config.j2 -d spine1 --vars '{"ntp_server": "10.0.0.1"}' -v
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # REQUIRED ARGUMENTS
    required_group = parser.add_argument_group('required arguments')
    required_group.add_argument(
        '--template', '-t',
        required=True,
        help='Template file name to use (e.g., ntp_config.j2)'
    )

    # DEVICE SELECTION (at least one required)
    device_group = parser.add_argument_group(
        'device selection',
        'At least one device selection method is required'
    )
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

    # DEPLOYMENT OPTIONS
    deploy_group = parser.add_argument_group('deployment options')
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
        '--backup-dir',
        help='Custom backup directory (default: configs/backups)'
    )

    # OUTPUT OPTIONS
    output_group = parser.add_argument_group('output options')
    output_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    output_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output (only errors)'
    )
    output_group.add_argument(
        '--output', '-o',
        help='Save deployment report to file'
    )

    # Parse arguments
    args = parser.parse_args()

    # ========================================================================
    # 2. VALIDATE ARGUMENTS
    # ========================================================================

    # Check for conflicting flags
    if args.verbose and args.quiet:
        print_error("Cannot use --verbose and --quiet together")
        return 2

    # Ensure at least one device selection method
    if not (args.devices or args.role or args.all):
        print_error("At least one device selection method is required (--device, --role, or --all)")
        print()
        parser.print_help()
        return 2

    # ========================================================================
    # 3. SETUP LOGGING
    # ========================================================================

    if args.quiet:
        log_level = "ERROR"
    elif args.verbose:
        log_level = "DEBUG"
    else:
        log_level = "INFO"

    logger = setup_logging(log_level=log_level)

    # ========================================================================
    # 4. INITIALIZE COMPONENTS
    # ========================================================================

    try:
        if not args.quiet:
            print()
            print_info("Initializing deployment system...")

        # Initialize components
        inventory_loader = InventoryLoader()
        template_engine = TemplateEngine()

        # Initialize deployment manager with backup settings
        auto_backup = not args.no_backup

        if args.backup_dir:
            # Note: ConfigDeployment doesn't support custom backup_dir in constructor
            # We'll log a warning
            logger.warning("Custom backup directory not supported in current version")

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

    # ========================================================================
    # 5. VALIDATE TEMPLATE EXISTS
    # ========================================================================

    if not validate_template_exists(template_engine, args.template):
        return 2

    # ========================================================================
    # 6. LOAD AND PARSE VARIABLES
    # ========================================================================

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

    # ========================================================================
    # 7. LOAD INVENTORY AND GET TARGET DEVICES
    # ========================================================================

    try:
        target_devices = []

        # Get devices by name
        if args.devices:
            for device_name in args.devices:
                device = inventory_loader.get_device_by_name(device_name)
                if device:
                    target_devices.append(device)
                    logger.debug(f"Added device: {device_name}")
                else:
                    print_error(f"Device not found: {device_name}")
                    return 2

        # Get devices by role
        if args.role:
            role_devices = inventory_loader.get_devices_by_role(args.role)
            if not role_devices:
                print_error(f"No devices found with role: {args.role}")
                return 2
            target_devices.extend(role_devices)
            logger.debug(f"Added {len(role_devices)} devices with role: {args.role}")

        # Get all devices
        if args.all:
            all_devices = inventory_loader.get_all_devices()
            if not all_devices:
                print_error("No devices found in inventory")
                return 2
            target_devices.extend(all_devices)
            logger.debug(f"Added all {len(all_devices)} devices from inventory")

        # Remove duplicates (in case same device selected multiple ways)
        # Use device name as unique identifier
        seen = set()
        unique_devices = []
        for device in target_devices:
            device_name = device.get('name')
            if device_name not in seen:
                seen.add(device_name)
                unique_devices.append(device)

        target_devices = unique_devices

        if not target_devices:
            print_error("No target devices selected")
            return 2

        logger.info(f"Selected {len(target_devices)} target device(s)")

    except Exception as e:
        logger.exception("Failed to load target devices")
        print_error(f"Failed to load devices: {e}")
        return 2

    # ========================================================================
    # 8. DISPLAY DEPLOYMENT PLAN
    # ========================================================================

    if not args.quiet:
        display_deployment_plan(
            devices=target_devices,
            template_name=args.template,
            variables=variables,
            dry_run=args.dry_run,
            backup_enabled=auto_backup,
            parallel=args.parallel
        )

    # ========================================================================
    # 9. SHOW WARNINGS IF APPLICABLE
    # ========================================================================

    if args.no_backup and not args.dry_run and not args.quiet:
        print()
        print_error("WARNING: Automatic backups are DISABLED!")
        print_error("Proceeding without backups is risky and not recommended.")
        print()

    # ========================================================================
    # 10. CONFIRM DEPLOYMENT
    # ========================================================================

    # Skip confirmation for dry-run or if quiet mode
    if not args.dry_run and not args.quiet:
        if not confirm_deployment():
            print()
            print_info("Deployment cancelled by user")
            return 0

    # ========================================================================
    # 11. EXECUTE DEPLOYMENT
    # ========================================================================

    try:
        start_time = datetime.now()

        if args.dry_run:
            # Dry-run mode: show previews
            if not args.quiet:
                print()
                print_info("DRY-RUN MODE: Generating configuration previews...")

            preview_deployments(deployer, target_devices, args.template, variables)

            # Create mock results for report
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

    # ========================================================================
    # 12. DISPLAY RESULTS
    # ========================================================================

    if not args.quiet:
        exit_code = display_results(results, start_time, deployer, args.output)
    else:
        # In quiet mode, only show errors
        failed = [r for r in results if not r['success']]
        if failed:
            for result in failed:
                print_error(f"{result['device_name']}: {result['error']}")
            exit_code = 1
        else:
            exit_code = 0

        # Still save report if requested
        if args.output:
            report = deployer.generate_deployment_report(results)
            safe_write_file(args.output, report)

    # ========================================================================
    # 13 & 14. EXIT WITH APPROPRIATE CODE
    # ========================================================================

    return exit_code


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print()
        print_error("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
