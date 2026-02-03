#!/usr/bin/env python3
"""
Example script demonstrating the ConfigBackup module.

This script shows various usage patterns for the automated configuration
backup system.

Usage:
    # From project root
    python3 examples/backup_example.py

    # Or make it executable and run directly
    chmod +x examples/backup_example.py
    ./examples/backup_example.py
"""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from backup import ConfigBackup
from utils import setup_logging, print_success, print_error, print_info, print_separator


def example_single_device_backup(backup_mgr):
    """Example 1: Backup a single device."""
    print_separator("=")
    print("EXAMPLE 1: Single Device Backup")
    print_separator("=")

    # Get a device from inventory
    device = backup_mgr.inventory_loader.get_device_by_name("spine1")

    if device:
        print_info(f"Backing up device: {device['name']} ({device['ip']})")

        # Perform backup
        result = backup_mgr.backup_device(device, verify=True)

        # Check result
        if result['success']:
            print_success(f"Backup saved: {result['filepath']}")
            print_info(f"File size: {result['file_size'] / 1024:.1f} KB")
        else:
            print_error(f"Backup failed: {result['error']}")
    else:
        print_error("Device 'spine1' not found in inventory")

    print()


def example_role_based_backup(backup_mgr):
    """Example 2: Backup all devices with a specific role."""
    print_separator("=")
    print("EXAMPLE 2: Role-Based Backup (Parallel)")
    print_separator("=")

    role = "spine"
    print_info(f"Backing up all '{role}' devices...")

    # Backup devices by role
    results = backup_mgr.backup_devices_by_role(role, parallel=True)

    # Generate and display report
    report = backup_mgr.generate_backup_report(results)
    print(report)


def example_all_devices_backup(backup_mgr):
    """Example 3: Backup all devices in inventory."""
    print_separator("=")
    print("EXAMPLE 3: Backup All Devices (Parallel)")
    print_separator("=")

    print_info("Backing up all devices from inventory...")

    # Backup all devices with parallel execution
    results = backup_mgr.backup_all_devices(parallel=True)

    # Generate report
    report = backup_mgr.generate_backup_report(results)
    print(report)


def example_sequential_backup(backup_mgr):
    """Example 4: Sequential backup for debugging or controlled execution."""
    print_separator("=")
    print("EXAMPLE 4: Sequential Backup")
    print_separator("=")

    print_info("Backing up spine devices sequentially...")

    # Get spine devices
    devices = backup_mgr.inventory_loader.get_devices_by_role("spine")

    # Backup sequentially
    results = backup_mgr.backup_multiple_devices(
        devices,
        parallel=False  # Sequential mode
    )

    # Show results
    for result in results:
        if result['success']:
            print_success(f"{result['device_name']}: Backup successful")
        else:
            print_error(f"{result['device_name']}: {result['error']}")

    print()


def example_list_backups(backup_mgr):
    """Example 5: List and manage backups for a device."""
    print_separator("=")
    print("EXAMPLE 5: List Device Backups")
    print_separator("=")

    device_name = "spine1"
    print_info(f"Listing backups for device '{device_name}'...")

    # List all backups
    backups = backup_mgr.list_device_backups(device_name)

    if backups:
        print_success(f"Found {len(backups)} backup(s):")
        for i, backup_path in enumerate(backups[:5], 1):  # Show first 5
            filename = os.path.basename(backup_path)
            size = os.path.getsize(backup_path) / 1024
            print(f"  {i}. {filename} ({size:.1f} KB)")

        if len(backups) > 5:
            print(f"  ... and {len(backups) - 5} more")

        # Get latest backup
        latest = backup_mgr.get_latest_backup(device_name)
        if latest:
            print_info(f"Latest: {os.path.basename(latest)}")

            # Verify latest backup
            if backup_mgr.verify_backup(latest):
                print_success("Latest backup verified successfully")
            else:
                print_error("Latest backup verification failed")
    else:
        print_error(f"No backups found for device '{device_name}'")

    print()


def example_cleanup_old_backups(backup_mgr):
    """Example 6: Cleanup old backups."""
    print_separator("=")
    print("EXAMPLE 6: Cleanup Old Backups")
    print_separator("=")

    print_info("Cleaning up backups older than retention period...")

    # Perform cleanup
    result = backup_mgr.cleanup_old_backups()

    # Display results
    if result['deleted_count'] > 0:
        freed_mb = result['freed_space'] / (1024 * 1024)
        print_success(
            f"Deleted {result['deleted_count']} old backup(s), "
            f"freed {freed_mb:.2f} MB"
        )
        for deleted in result['deleted_files'][:5]:  # Show first 5
            print(f"  - {os.path.basename(deleted)}")
    else:
        print_info("No old backups to delete")

    if result['errors']:
        print_error(f"Encountered {len(result['errors'])} error(s)")
        for error in result['errors']:
            print(f"  - {error}")

    print()


def example_custom_configuration(backup_mgr):
    """Example 7: Custom backup configuration."""
    print_separator("=")
    print("EXAMPLE 7: Custom Backup Manager Configuration")
    print_separator("=")

    # Create custom backup manager with different settings
    custom_backup_mgr = ConfigBackup(
        inventory_path="inventory/devices.yaml",
        backup_dir="configs/custom_backups",
        retention_days=7  # Shorter retention period
    )

    print_info("Custom backup manager created:")
    print(f"  Backup directory: {custom_backup_mgr.backup_dir}")
    print(f"  Retention days: {custom_backup_mgr.retention_days}")
    print(f"  Device count: {custom_backup_mgr.inventory_loader.get_device_count()}")
    print()


def main():
    """Main function to run all examples."""
    print()
    print("=" * 80)
    print("Configuration Backup System - Examples")
    print("=" * 80)
    print()

    # Setup logging
    logger = setup_logging(
        log_level="INFO",
        log_file="logs/backup_examples.log"
    )

    try:
        # Initialize backup manager
        print_info("Initializing backup manager...")
        backup_mgr = ConfigBackup(
            inventory_path="inventory/devices.yaml",
            backup_dir="configs/backups",
            retention_days=30
        )
        print_success("Backup manager initialized successfully")
        print()

        # Run examples
        # NOTE: Comment out examples that require actual device connections
        # if you're just testing the structure

        # Example 1: Single device backup
        # example_single_device_backup(backup_mgr)

        # Example 2: Role-based backup
        # example_role_based_backup(backup_mgr)

        # Example 3: Backup all devices
        # example_all_devices_backup(backup_mgr)

        # Example 4: Sequential backup
        # example_sequential_backup(backup_mgr)

        # Example 5: List backups (doesn't require device connection)
        example_list_backups(backup_mgr)

        # Example 6: Cleanup old backups (doesn't require device connection)
        example_cleanup_old_backups(backup_mgr)

        # Example 7: Custom configuration (doesn't require device connection)
        example_custom_configuration(backup_mgr)

        print_separator("=")
        print("Examples completed successfully!")
        print_separator("=")
        print()

        print_info("To run backup examples that connect to devices:")
        print("  1. Ensure devices are reachable")
        print("  2. Verify credentials in inventory/devices.yaml")
        print("  3. Uncomment desired examples in this script")
        print()

    except FileNotFoundError as e:
        print_error(f"File not found: {e}")
        print("\nMake sure you're running this script from the project root:")
        print("  python3 examples/backup_example.py")
        sys.exit(1)

    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
