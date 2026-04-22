import os
import ipaddress
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import yaml
except ImportError:
    raise ImportError(
        "PyYAML is required. Install it with: pip install pyyaml"
    )


class InventoryLoader:
    """
    Load and manage network device inventory from YAML files.

    This class provides methods to load device inventory, filter devices by
    various criteria, and validate the inventory structure.

    Attributes:
        inventory_path (Path): Path to the inventory YAML file
        settings (dict): Global settings from inventory
        devices (list): List of all devices from inventory
    """

    def __init__(self, inventory_path: str = "inventory/devices.yaml") -> None:
        """
        Initialize the InventoryLoader and load the inventory file.

        Args:
            inventory_path: Path to the YAML inventory file (default: inventory/devices.yaml)

        Raises:
            FileNotFoundError: If the inventory file doesn't exist
            yaml.YAMLError: If the YAML file is malformed
            KeyError: If required sections (settings, devices) are missing
        """
        self.inventory_path = Path(inventory_path)
        self.settings: Dict[str, Any] = {}
        self.devices: List[Dict[str, Any]] = []

        self._load_inventory()

    def _load_inventory(self) -> None:
        """
        Load and parse the YAML inventory file.

        Raises:
            FileNotFoundError: If inventory file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            KeyError: If required sections are missing
        """
        if not self.inventory_path.exists():
            raise FileNotFoundError(
                f"Inventory file not found: {self.inventory_path.absolute()}\n"
                f"Please ensure the file exists or provide the correct path."
            )

        try:
            with open(self.inventory_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(
                f"Failed to parse YAML file {self.inventory_path}: {e}"
            )

        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid inventory format: expected dictionary, got {type(data)}"
            )

        # Extract settings section
        if 'settings' not in data:
            raise KeyError(
                "Missing 'settings' section in inventory file. "
                "Please add a settings section with global configuration."
            )
        self.settings = data['settings']

        # Extract devices section
        if 'devices' not in data:
            raise KeyError(
                "Missing 'devices' section in inventory file. "
                "Please add a devices section with device list."
            )

        self.devices = data['devices']

        if not isinstance(self.devices, list):
            raise ValueError(
                f"Devices section must be a list, got {type(self.devices)}"
            )

    def get_all_devices(self) -> List[Dict[str, Any]]:
        """
        Get all devices from the inventory.

        Returns:
            List of device dictionaries containing device properties

        Example:
            >>> loader = InventoryLoader()
            >>> devices = loader.get_all_devices()
            >>> for device in devices:
            ...     print(f"{device['name']}: {device['ip']}")
        """
        return self.devices.copy()

    def get_device_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find and return a device by its exact name.

        Args:
            name: The exact device name to search for (case-sensitive)

        Returns:
            Device dictionary if found, None otherwise

        Example:
            >>> loader = InventoryLoader()
            >>> device = loader.get_device_by_name("spine1")
            >>> if device:
            ...     print(f"Found: {device['ip']}")
            ... else:
            ...     print("Device not found")
        """
        for device in self.devices:
            if device.get('name') == name:
                return device.copy()
        return None

    def get_devices_by_role(self, role: str) -> List[Dict[str, Any]]:
        """
        Filter and return devices by their role.

        Args:
            role: The role to filter by (e.g., 'spine', 'leaf', 'border')

        Returns:
            List of devices matching the specified role

        Example:
            >>> loader = InventoryLoader()
            >>> spines = loader.get_devices_by_role("spine")
            >>> print(f"Found {len(spines)} spine switches")
            >>>
            >>> leaves = loader.get_devices_by_role("leaf")
            >>> for leaf in leaves:
            ...     print(f"Leaf: {leaf['name']}")
        """
        return [
            device.copy()
            for device in self.devices
            if device.get('role') == role
        ]

    def get_settings(self) -> Dict[str, Any]:
        """
        Get the global settings from the inventory.

        Returns:
            Dictionary containing global settings (credentials, connection config, etc.)

        Example:
            >>> loader = InventoryLoader()
            >>> settings = loader.get_settings()
            >>> print(f"Default username: {settings['default_username']}")
        """
        return self.settings.copy()

    def validate_inventory(self) -> bool:
        """
        Validate the inventory structure and data.

        Checks:
        - Required fields exist in settings
        - Required fields exist for each device
        - IP addresses are valid IPv4 format
        - No duplicate device names
        - No duplicate IP addresses
        - Device types are specified

        Returns:
            True if validation passes

        Raises:
            ValueError: If validation fails, with detailed error message

        Example:
            >>> loader = InventoryLoader()
            >>> try:
            ...     if loader.validate_inventory():
            ...         print("Inventory validation passed!")
            ... except ValueError as e:
            ...     print(f"Validation failed: {e}")
        """
        errors = []

        # Validate settings section
        required_settings = [
            'default_username',
            'default_password',
            'default_device_type',
            'connection_timeout',
        ]

        for setting in required_settings:
            if setting not in self.settings:
                errors.append(f"Missing required setting: {setting}")

        # Validate devices section
        if not self.devices:
            errors.append("No devices defined in inventory")
            # Return early if no devices to validate
            if errors:
                raise ValueError(
                    f"Inventory validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
                )

        required_device_fields = ['name', 'ip', 'role', 'location', 'device_type']

        device_names = set()
        device_ips = set()

        for idx, device in enumerate(self.devices):
            device_id = device.get('name', f'device_{idx}')

            # Check required fields
            for field in required_device_fields:
                if field not in device:
                    errors.append(
                        f"Device '{device_id}': missing required field '{field}'"
                    )

            # Validate IP address format
            if 'ip' in device:
                ip_addr = device['ip']
                try:
                    ipaddress.IPv4Address(ip_addr)
                except ipaddress.AddressValueError:
                    errors.append(
                        f"Device '{device_id}': invalid IP address '{ip_addr}'"
                    )

                # Check for duplicate IPs
                if ip_addr in device_ips:
                    errors.append(
                        f"Device '{device_id}': duplicate IP address '{ip_addr}'"
                    )
                device_ips.add(ip_addr)

            # Check for duplicate names
            if 'name' in device:
                name = device['name']
                if name in device_names:
                    errors.append(
                        f"Duplicate device name: '{name}'"
                    )
                device_names.add(name)

            # Validate device_type is not empty
            if 'device_type' in device and not device['device_type']:
                errors.append(
                    f"Device '{device_id}': device_type cannot be empty"
                )

        # Raise all errors if any found
        if errors:
            raise ValueError(
                f"Inventory validation failed ({len(errors)} errors):\n" +
                "\n".join(f"  - {e}" for e in errors)
            )

        return True

    def get_devices_by_location(self, location: str) -> List[Dict[str, Any]]:
        """
        Filter and return devices by their location.

        Args:
            location: The location to filter by (e.g., 'lab', 'datacenter-1')

        Returns:
            List of devices in the specified location

        Example:
            >>> loader = InventoryLoader()
            >>> lab_devices = loader.get_devices_by_location("lab")
            >>> print(f"Devices in lab: {len(lab_devices)}")
        """
        return [
            device.copy()
            for device in self.devices
            if device.get('location') == location
        ]

    def get_device_count(self) -> int:
        """
        Get the total number of devices in inventory.

        Returns:
            Total device count
        """
        return len(self.devices)

    def get_devices_by_vendor(self, vendor: str) -> List[Dict[str, Any]]:
        """
        Filter and return devices by vendor.

        Args:
            vendor: The vendor name to filter by (e.g., 'Nokia', 'Cisco')

        Returns:
            List of devices from the specified vendor

        Example:
            >>> loader = InventoryLoader()
            >>> nokia_devices = loader.get_devices_by_vendor("Nokia")
        """
        return [
            device.copy()
            for device in self.devices
            if device.get('vendor') == vendor
        ]

    def __repr__(self) -> str:
        """String representation of InventoryLoader."""
        return (
            f"InventoryLoader(path='{self.inventory_path}', "
            f"devices={len(self.devices)}, "
            f"settings_keys={list(self.settings.keys())})"
        )

    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"InventoryLoader with {len(self.devices)} devices from {self.inventory_path}"


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of the InventoryLoader class.
    Run this script directly to test inventory loading.
    """
    try:
        # Initialize loader
        print("Loading inventory...")
        loader = InventoryLoader()

        print(f"\n{loader}")
        print(f"Inventory path: {loader.inventory_path.absolute()}")

        # Validate inventory
        print("\nValidating inventory...")
        loader.validate_inventory()
        print("✓ Inventory validation passed!")

        # Display settings
        print("\n" + "="*60)
        print("GLOBAL SETTINGS")
        print("="*60)
        settings = loader.get_settings()
        for key, value in settings.items():
            # Hide password in output
            if 'password' in key.lower():
                value = '*' * 8
            print(f"  {key}: {value}")

        # Display device summary
        print("\n" + "="*60)
        print("DEVICE SUMMARY")
        print("="*60)
        all_devices = loader.get_all_devices()
        print(f"  Total devices: {loader.get_device_count()}")

        # Group by role
        roles = set(device.get('role', 'unknown') for device in all_devices)
        for role in sorted(roles):
            role_devices = loader.get_devices_by_role(role)
            print(f"  {role.capitalize()} switches: {len(role_devices)}")

        # Display all devices
        print("\n" + "="*60)
        print("ALL DEVICES")
        print("="*60)
        print(f"{'Name':<12} {'IP':<15} {'Role':<10} {'Location':<12}")
        print("-" * 54)
        for device in all_devices:
            print(
                f"{device['name']:<12} "
                f"{device['ip']:<15} "
                f"{device['role']:<10} "
                f"{device.get('location', 'N/A'):<12}"
            )

        # Example: Get specific device
        print("\n" + "="*60)
        print("DEVICE LOOKUP EXAMPLE")
        print("="*60)
        spine1 = loader.get_device_by_name("spine1")
        if spine1:
            print("Device: spine1")
            for key, value in spine1.items():
                print(f"  {key}: {value}")

        # Example: Filter by role
        print("\n" + "="*60)
        print("SPINE SWITCHES")
        print("="*60)
        spines = loader.get_devices_by_role("spine")
        for spine in spines:
            print(f"  {spine['name']}: {spine['ip']} - {spine.get('description', 'N/A')}")

        print("\n✓ All tests completed successfully!")

    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        print("\nMake sure you're running this script from the project root directory.")
        print("Expected inventory location: inventory/devices.yaml")
    except ValueError as e:
        print(f"✗ Validation Error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
