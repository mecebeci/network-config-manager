import sys
import argparse
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.deployment import ConfigDeployment
from src.utils import (
    setup_logging,
    print_separator,
    print_success,
    print_error,
    print_info,
    safe_write_file,
)


def main():
    """Main entry point for deployment CLI."""
    parser = argparse.ArgumentParser(
        description="Deploy network device configurations using Jinja2 templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview deployment (dry-run)
  %(prog)s --device spine1 --template example_ntp.j2 --var ntp_server=10.0.0.1 --dry-run

  # Deploy to single device
  %(prog)s --device spine1 --template example_ntp.j2 --var ntp_server=10.0.0.1

  # Deploy to multiple devices by role
  %(prog)s --role spine --template example_ntp.j2 --var ntp_server=10.0.0.1

  # Deploy to all devices
  %(prog)s --all --template example_ntp.j2 --var ntp_server=10.0.0.1

  # Deploy with parallel execution
  %(prog)s --role leaf --template example_snmp.j2 --var snmp_community=public --parallel

  # Deploy without automatic backup
  %(prog)s --device leaf1 --template example_interface.j2 --var interface_name=ethernet-1/1 --no-backup

  # List available templates
  %(prog)s --list-templates

  # List available devices
  %(prog)s --list-devices

  # Show device details
  %(prog)s --show-device spine1
        """
    )

    # Deployment target options (mutually exclusive)
    target_group = parser.add_mutually_exclusive_group(required=False)
    target_group.add_argument(
        '--device',
        help='Deploy to specific device by name'
    )
    target_group.add_argument(
        '--role',
        help='Deploy to all devices with specified role (spine, leaf, border, etc.)'
    )
    target_group.add_argument(
        '--all',
        action='store_true',
        help='Deploy to all devices in inventory'
    )

    # Template options
    parser.add_argument(
        '--template',
        help='Jinja2 template file name (e.g., example_ntp.j2)'
    )

    # Variable options
    parser.add_argument(
        '--var',
        action='append',
        dest='variables',
        metavar='KEY=VALUE',
        help='Template variable in KEY=VALUE format (can be specified multiple times)'
    )

    # Deployment options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview configuration without deploying'
    )

    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip automatic backup before deployment'
    )

    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Deploy to multiple devices in parallel'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='Maximum number of parallel workers (default: 5)'
    )

    # Report options
    parser.add_argument(
        '--save-report',
        metavar='FILE',
        help='Save deployment report to specified file'
    )

    # Information/listing options
    parser.add_argument(
        '--list-templates',
        action='store_true',
        help='List all available templates and exit'
    )

    parser.add_argument(
        '--list-devices',
        action='store_true',
        help='List all devices in inventory and exit'
    )

    parser.add_argument(
        '--show-device',
        metavar='DEVICE_NAME',
        help='Show details for specified device and exit'
    )

    # Logging options
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress non-essential output'
    )

    # Parse arguments
    args = parser.parse_args()

    # Setup logging
    log_level = 'WARNING' if args.quiet else args.log_level
    logger = setup_logging(log_level=log_level)

    try:
        # Initialize deployment manager
        if not args.quiet:
            print_info("Initializing deployment manager...")

        deployer = ConfigDeployment(auto_backup=not args.no_backup)

        if not args.quiet:
            print_success("Deployment manager initialized")
            print()

        # Handle information/listing commands
        if args.list_templates:
            print_separator("=", 80)
            print("AVAILABLE TEMPLATES")
            print_separator("=", 80)
            templates = deployer.template_engine.list_templates()
            if templates:
                for template in templates:
                    print(f"  • {template}")
                print()
                print(f"Total: {len(templates)} templates")
            else:
                print_info("No templates found")
            print_separator("=", 80)
            return 0

        if args.list_devices:
            print_separator("=", 80)
            print("DEVICE INVENTORY")
            print_separator("=", 80)
            devices = deployer.inventory_loader.get_all_devices()

            if devices:
                # Group by role
                roles = {}
                for device in devices:
                    role = device.get('role', 'unknown')
                    if role not in roles:
                        roles[role] = []
                    roles[role].append(device)

                for role in sorted(roles.keys()):
                    print(f"\n{role.upper()} ({len(roles[role])} devices):")
                    print("-" * 80)
                    for device in roles[role]:
                        print(
                            f"  • {device['name']:<15} {device['ip']:<15} "
                            f"({device.get('device_type', 'N/A')})"
                        )

                print()
                print(f"Total: {len(devices)} devices")
            else:
                print_info("No devices found in inventory")

            print_separator("=", 80)
            return 0

        if args.show_device:
            device = deployer.inventory_loader.get_device_by_name(args.show_device)

            if not device:
                print_error(f"Device '{args.show_device}' not found in inventory")
                return 1

            print_separator("=", 80)
            print(f"DEVICE DETAILS: {args.show_device}")
            print_separator("=", 80)

            for key, value in device.items():
                # Hide password
                if 'password' in key.lower():
                    value = '********'
                print(f"  {key:<20}: {value}")

            print_separator("=", 80)
            return 0

        # Validate deployment requirements
        if not args.template:
            print_error("Template is required for deployment (--template)")
            parser.print_help()
            return 1

        if not any([args.device, args.role, args.all]):
            print_error("Deployment target required (--device, --role, or --all)")
            parser.print_help()
            return 1

        # Parse variables
        variables = {}
        if args.variables:
            for var in args.variables:
                if '=' not in var:
                    print_error(f"Invalid variable format: {var} (expected KEY=VALUE)")
                    return 1

                key, value = var.split('=', 1)
                variables[key.strip()] = value.strip()

        # Display deployment information
        if not args.quiet:
            print_separator("=", 80)
            print("DEPLOYMENT CONFIGURATION")
            print_separator("=", 80)
            print(f"  Template:      {args.template}")
            print(f"  Variables:     {len(variables)} variables")
            for key, value in variables.items():
                print(f"    - {key} = {value}")
            print(f"  Dry-run:       {args.dry_run}")
            print(f"  Auto-backup:   {not args.no_backup}")
            if args.role or args.all:
                print(f"  Parallel:      {args.parallel}")
                if args.parallel:
                    print(f"  Workers:       {args.workers}")
            print_separator("=", 80)
            print()

        # Get target devices
        if args.device:
            device = deployer.inventory_loader.get_device_by_name(args.device)
            if not device:
                print_error(f"Device '{args.device}' not found in inventory")
                return 1
            devices = [device]
            target_description = f"device '{args.device}'"

        elif args.role:
            devices = deployer.inventory_loader.get_devices_by_role(args.role)
            if not devices:
                print_error(f"No devices found with role '{args.role}'")
                return 1
            target_description = f"{len(devices)} devices with role '{args.role}'"

        else:  # args.all
            devices = deployer.inventory_loader.get_all_devices()
            if not devices:
                print_error("No devices found in inventory")
                return 1
            target_description = f"all {len(devices)} devices"

        # Confirm deployment (unless dry-run or quiet)
        if not args.dry_run and not args.quiet and len(devices) > 1:
            response = input(f"\nDeploy to {target_description}? [y/N]: ")
            if response.lower() != 'y':
                print_info("Deployment cancelled")
                return 0

        # Perform deployment
        if not args.quiet:
            mode = "DRY-RUN" if args.dry_run else "DEPLOYMENT"
            print_info(f"Starting {mode} to {target_description}...")
            print()

        if len(devices) == 1:
            # Single device deployment
            result = deployer.deploy_to_device(
                device=devices[0],
                template_name=args.template,
                variables=variables,
                dry_run=args.dry_run
            )

            # Display result
            if args.dry_run and result['success']:
                print_separator("=", 80)
                print("CONFIGURATION PREVIEW")
                print_separator("=", 80)
                print(result['config_preview'])
                print_separator("=", 80)
            elif result['success']:
                print_success(f"Deployment successful to {result['device_name']}")
                if result.get('backup_created'):
                    print_info(f"Backup saved: {result['backup_created']}")
            else:
                print_error(f"Deployment failed: {result['error']}")
                return 1

            results = [result]

        else:
            # Multiple device deployment
            results = deployer.deploy_to_multiple_devices(
                devices=devices,
                template_name=args.template,
                variables_list=variables,
                dry_run=args.dry_run,
                parallel=args.parallel,
                max_workers=args.workers
            )

        # Generate and display report
        if not args.quiet:
            print()
            report = deployer.generate_deployment_report(results)
            print(report)

            # Save report if requested
            if args.save_report:
                if safe_write_file(args.save_report, report):
                    print_success(f"Report saved to {args.save_report}")
                else:
                    print_error(f"Failed to save report to {args.save_report}")

        # Determine exit code based on results
        failed_count = sum(1 for r in results if not r['success'])
        if failed_count > 0:
            return 1
        else:
            return 0

    except FileNotFoundError as e:
        print_error(f"File not found: {e}")
        print("\nMake sure you're in the project root directory and")
        print("the inventory file exists at: inventory/devices.yaml")
        return 1

    except KeyboardInterrupt:
        print()
        print_info("Operation cancelled by user")
        return 130

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if args.log_level == 'DEBUG':
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
