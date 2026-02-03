import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from pysnmp.hlapi import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    getCmd,
    nextCmd,
    bulkCmd
)
from pysnmp.proto.rfc1902 import Integer, OctetString, Counter32, Gauge32, TimeTicks

from src.snmp_oids import (
    SYSTEM_OIDS,
    INTERFACE_OIDS,
    INTERFACE_INDEX_OID,
    ADMIN_STATUS,
    OPER_STATUS,
    get_interface_oid,
    parse_interface_index_from_oid,
    get_status_name
)
from src.inventory_loader import InventoryLoader
from src.utils import get_logger, get_human_timestamp, create_progress_bar


class SNMPMonitor:
    """
    SNMP Monitoring class for collecting metrics from network devices.

    This class provides methods to query SNMP-enabled network devices for
    system information, interface statistics, and operational metrics.
    Supports both single device queries and parallel collection from
    multiple devices.

    Attributes:
        inventory_loader (InventoryLoader): Device inventory manager
        logger (logging.Logger): Logger instance for this module
        default_community (str): Default SNMP community string
        default_port (int): Default SNMP port (161)
        timeout (int): SNMP operation timeout in seconds
        retries (int): Number of retry attempts for SNMP operations
    """

    def __init__(
        self,
        inventory_path: str = "inventory/devices.yaml",
        default_community: str = "public",
        timeout: int = 5,
        retries: int = 3
    ) -> None:
        """
        Initialize SNMP Monitor.

        Args:
            inventory_path: Path to device inventory YAML file
            default_community: Default SNMP community string (default: "public")
            timeout: SNMP operation timeout in seconds (default: 5)
            retries: Number of retry attempts (default: 3)

        Example:
            monitor = SNMPMonitor(
                inventory_path="inventory/devices.yaml",
                default_community="public",
                timeout=10,
                retries=3
            )
        """
        self.inventory_loader = InventoryLoader(inventory_path)
        self.logger = get_logger(__name__)
        self.default_community = default_community
        self.default_port = 161
        self.timeout = timeout
        self.retries = retries

        self.logger.info(
            f"SNMPMonitor initialized - Community: {default_community}, "
            f"Timeout: {timeout}s, Retries: {retries}"
        )

    def _build_snmp_target(self, device: Dict[str, Any]) -> Tuple[str, int, str]:
        """
        Build SNMP target parameters from device information.

        Extracts IP address, port, and community string from device dictionary.
        Falls back to defaults if not specified in device config.

        Args:
            device: Device dictionary from inventory

        Returns:
            Tuple of (ip, port, community)

        Example:
            ip, port, community = self._build_snmp_target(device)
        """
        ip = device.get('ip', '')
        port = device.get('snmp_port', self.default_port)

        # Get community from device settings, global settings, or use default
        community = device.get('snmp_community')
        if not community:
            settings = self.inventory_loader.get_settings()
            community = settings.get('snmp_community', self.default_community)

        return ip, port, community

    def _convert_timeticks(self, timeticks: int) -> Tuple[int, str]:
        """
        Convert SNMP timeticks to seconds and human-readable format.

        SNMP timeticks are in hundredths of seconds since system boot.

        Args:
            timeticks: SNMP timeticks value

        Returns:
            Tuple of (seconds, readable_string)

        Example:
            seconds, readable = self._convert_timeticks(86412345)
            # Returns: (864123, "10 days, 0 hours, 2 minutes")
        """
        # Convert timeticks (hundredths of seconds) to seconds
        seconds = int(timeticks / 100)

        # Calculate time components
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        # Build readable string
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if secs > 0 or not parts:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")

        readable = ", ".join(parts)
        return seconds, readable

    def _format_mac_address(self, mac_bytes: Any) -> str:
        """
        Format MAC address from bytes to standard string format.

        Handles different input formats (bytes, hex string, OctetString).

        Args:
            mac_bytes: MAC address in various formats

        Returns:
            MAC address as string in format "AA:BB:CC:DD:EE:FF"

        Example:
            mac = self._format_mac_address(b'\\x00\\x11\\x22\\x33\\x44\\x55')
            # Returns: "00:11:22:33:44:55"
        """
        try:
            if isinstance(mac_bytes, (bytes, OctetString)):
                # Convert bytes to hex string with colons
                return ':'.join(f'{b:02X}' for b in mac_bytes)
            elif isinstance(mac_bytes, str):
                # Already a string, ensure proper format
                return mac_bytes.upper()
            else:
                return "N/A"
        except Exception as e:
            self.logger.debug(f"Failed to format MAC address: {e}")
            return "N/A"

    def snmp_get(self, device: Dict[str, Any], oid: str) -> Tuple[bool, Any, Optional[str]]:
        """
        Perform SNMP GET operation for a single OID.

        Args:
            device: Device dictionary from inventory
            oid: SNMP OID string to query

        Returns:
            Tuple of (success, value, error_message)
            - success: True if operation succeeded
            - value: Retrieved value (or None if failed)
            - error_message: Error description if failed (or None if succeeded)

        Example:
            success, value, error = monitor.snmp_get(device, '1.3.6.1.2.1.1.5.0')
            if success:
                print(f"System name: {value}")
            else:
                print(f"Error: {error}")
        """
        ip, port, community = self._build_snmp_target(device)
        device_name = device.get('name', ip)

        self.logger.debug(f"SNMP GET {device_name} ({ip}): {oid}")

        try:
            # Build SNMP GET request
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((ip, port), timeout=self.timeout, retries=self.retries),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )

            # Execute request
            error_indication, error_status, error_index, var_binds = next(iterator)

            # Check for errors
            if error_indication:
                error_msg = f"SNMP error: {error_indication}"
                self.logger.warning(f"{device_name}: {error_msg}")
                return False, None, error_msg

            if error_status:
                error_msg = f"SNMP error: {error_status.prettyPrint()}"
                self.logger.warning(f"{device_name}: {error_msg}")
                return False, None, error_msg

            # Extract value
            if var_binds:
                oid_obj, value = var_binds[0]
                self.logger.debug(f"{device_name}: {oid} = {value}")
                return True, value, None
            else:
                error_msg = "No data returned"
                self.logger.warning(f"{device_name}: {error_msg}")
                return False, None, error_msg

        except Exception as e:
            error_msg = f"Exception during SNMP GET: {str(e)}"
            self.logger.error(f"{device_name}: {error_msg}")
            return False, None, error_msg

    def snmp_get_multiple(
        self,
        device: Dict[str, Any],
        oids: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Get multiple OIDs in separate requests.

        Args:
            device: Device dictionary from inventory
            oids: Dictionary of {name: oid} pairs

        Returns:
            Dictionary of {name: value} with results
            Failed OIDs will have None values

        Example:
            oids = {
                'sysName': '1.3.6.1.2.1.1.5.0',
                'sysLocation': '1.3.6.1.2.1.1.6.0'
            }
            results = monitor.snmp_get_multiple(device, oids)
            print(f"Name: {results['sysName']}")
            print(f"Location: {results['sysLocation']}")
        """
        results = {}
        device_name = device.get('name', device.get('ip', 'unknown'))

        self.logger.debug(f"SNMP GET multiple on {device_name}: {len(oids)} OIDs")

        for name, oid in oids.items():
            success, value, error = self.snmp_get(device, oid)
            if success:
                results[name] = value
            else:
                results[name] = None
                self.logger.debug(f"{device_name}: Failed to get {name}: {error}")

        return results

    def snmp_walk(self, device: Dict[str, Any], oid: str) -> Dict[str, Any]:
        """
        Perform SNMP WALK operation to get table data.

        Walks the OID tree starting from the specified OID and returns all
        sub-OIDs and their values.

        Args:
            device: Device dictionary from inventory
            oid: Base OID string to walk

        Returns:
            Dictionary of {full_oid: value}

        Example:
            # Walk interface descriptions
            results = monitor.snmp_walk(device, '1.3.6.1.2.1.2.2.1.2')
            for oid, value in results.items():
                print(f"{oid}: {value}")
        """
        ip, port, community = self._build_snmp_target(device)
        device_name = device.get('name', ip)
        results = {}

        self.logger.debug(f"SNMP WALK {device_name} ({ip}): {oid}")

        try:
            # Perform SNMP WALK
            iterator = nextCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((ip, port), timeout=self.timeout, retries=self.retries),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            )

            for error_indication, error_status, error_index, var_binds in iterator:
                # Check for errors
                if error_indication:
                    self.logger.warning(f"{device_name}: SNMP WALK error: {error_indication}")
                    break

                if error_status:
                    self.logger.warning(
                        f"{device_name}: SNMP WALK error: {error_status.prettyPrint()}"
                    )
                    break

                # Extract values
                for var_bind in var_binds:
                    oid_obj, value = var_bind
                    full_oid = str(oid_obj)
                    results[full_oid] = value

            self.logger.debug(f"{device_name}: SNMP WALK returned {len(results)} results")
            return results

        except Exception as e:
            self.logger.error(f"{device_name}: Exception during SNMP WALK: {str(e)}")
            return results

    def get_system_info(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect system information from device.

        Queries all system OIDs and formats the results including uptime
        conversion.

        Args:
            device: Device dictionary from inventory

        Returns:
            Dictionary containing:
                - device_name: Device name
                - ip: Device IP address
                - sysDescr: System description
                - sysName: System name
                - sysUpTime: Uptime in seconds
                - sysUpTime_readable: Human-readable uptime
                - sysContact: System contact
                - sysLocation: System location
                - sysObjectID: System object ID
                - success: Operation success status
                - error: Error message if failed
                - timestamp: Collection timestamp

        Example:
            sys_info = monitor.get_system_info(device)
            if sys_info['success']:
                print(f"Device: {sys_info['sysName']}")
                print(f"Uptime: {sys_info['sysUpTime_readable']}")
                print(f"Location: {sys_info['sysLocation']}")
        """
        device_name = device.get('name', 'unknown')
        ip = device.get('ip', 'unknown')
        timestamp = get_human_timestamp()

        self.logger.info(f"Collecting system info from {device_name} ({ip})")

        # Query all system OIDs
        results = self.snmp_get_multiple(device, SYSTEM_OIDS)

        # Check if we got any data
        if all(v is None for v in results.values()):
            return {
                'device_name': device_name,
                'ip': ip,
                'success': False,
                'error': 'Failed to retrieve any system information',
                'timestamp': timestamp
            }

        # Convert uptime
        uptime_ticks = results.get('sysUpTime')
        if uptime_ticks is not None:
            try:
                uptime_seconds, uptime_readable = self._convert_timeticks(int(uptime_ticks))
            except (ValueError, TypeError) as e:
                self.logger.warning(f"{device_name}: Failed to convert uptime: {e}")
                uptime_seconds = 0
                uptime_readable = "N/A"
        else:
            uptime_seconds = 0
            uptime_readable = "N/A"

        # Build result dictionary
        system_info = {
            'device_name': device_name,
            'ip': ip,
            'sysDescr': str(results.get('sysDescr', 'N/A')),
            'sysName': str(results.get('sysName', 'N/A')),
            'sysUpTime': uptime_seconds,
            'sysUpTime_readable': uptime_readable,
            'sysContact': str(results.get('sysContact', 'N/A')),
            'sysLocation': str(results.get('sysLocation', 'N/A')),
            'sysObjectID': str(results.get('sysObjectID', 'N/A')),
            'success': True,
            'error': None,
            'timestamp': timestamp
        }

        self.logger.info(f"{device_name}: System info collected successfully")
        return system_info

    def get_interface_list(self, device: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get list of all interfaces on device.

        Walks the ifDescr OID to enumerate all interfaces.

        Args:
            device: Device dictionary from inventory

        Returns:
            List of dictionaries with 'index' and 'name' keys

        Example:
            interfaces = monitor.get_interface_list(device)
            for iface in interfaces:
                print(f"Interface {iface['index']}: {iface['name']}")
        """
        device_name = device.get('name', device.get('ip', 'unknown'))

        self.logger.debug(f"Getting interface list from {device_name}")

        # Walk ifDescr to get all interfaces
        results = self.snmp_walk(device, INTERFACE_OIDS['ifDescr'])

        interfaces = []
        for oid, value in results.items():
            try:
                # Extract interface index from OID
                index = parse_interface_index_from_oid(oid)
                interfaces.append({
                    'index': index,
                    'name': str(value)
                })
            except Exception as e:
                self.logger.warning(f"{device_name}: Failed to parse interface OID {oid}: {e}")

        self.logger.debug(f"{device_name}: Found {len(interfaces)} interfaces")
        return interfaces

    def get_interface_stats(
        self,
        device: Dict[str, Any],
        interface_index: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Collect interface statistics.

        Gets detailed statistics for one or all interfaces including status,
        speed, traffic counters, and error counters.

        Args:
            device: Device dictionary from inventory
            interface_index: Specific interface index (None = all interfaces)

        Returns:
            List of interface statistics dictionaries, each containing:
                - index: Interface index
                - name: Interface name
                - admin_status: Administrative status
                - oper_status: Operational status
                - speed: Interface speed in bps
                - mtu: MTU size
                - mac_address: MAC address
                - in_octets: Input bytes counter
                - in_packets: Input packet counter
                - in_errors: Input error counter
                - out_octets: Output bytes counter
                - out_packets: Output packet counter
                - out_errors: Output error counter
                - timestamp: Collection timestamp

        Example:
            # Get all interface stats
            all_stats = monitor.get_interface_stats(device)

            # Get specific interface stats
            iface_stats = monitor.get_interface_stats(device, interface_index=1)
        """
        device_name = device.get('name', device.get('ip', 'unknown'))
        timestamp = get_human_timestamp()

        if interface_index is not None:
            self.logger.info(f"Collecting stats for interface {interface_index} on {device_name}")
            interfaces = [{'index': interface_index, 'name': 'N/A'}]
        else:
            self.logger.info(f"Collecting interface stats from {device_name}")
            interfaces = self.get_interface_list(device)

        if not interfaces:
            self.logger.warning(f"{device_name}: No interfaces found")
            return []

        interface_stats = []

        for iface in interfaces:
            idx = iface['index']

            # Build OIDs for this interface
            oids = {
                'ifDescr': get_interface_oid(INTERFACE_OIDS['ifDescr'], idx),
                'ifType': get_interface_oid(INTERFACE_OIDS['ifType'], idx),
                'ifMtu': get_interface_oid(INTERFACE_OIDS['ifMtu'], idx),
                'ifSpeed': get_interface_oid(INTERFACE_OIDS['ifSpeed'], idx),
                'ifPhysAddress': get_interface_oid(INTERFACE_OIDS['ifPhysAddress'], idx),
                'ifAdminStatus': get_interface_oid(INTERFACE_OIDS['ifAdminStatus'], idx),
                'ifOperStatus': get_interface_oid(INTERFACE_OIDS['ifOperStatus'], idx),
                'ifInOctets': get_interface_oid(INTERFACE_OIDS['ifInOctets'], idx),
                'ifInUcastPkts': get_interface_oid(INTERFACE_OIDS['ifInUcastPkts'], idx),
                'ifInErrors': get_interface_oid(INTERFACE_OIDS['ifInErrors'], idx),
                'ifOutOctets': get_interface_oid(INTERFACE_OIDS['ifOutOctets'], idx),
                'ifOutUcastPkts': get_interface_oid(INTERFACE_OIDS['ifOutUcastPkts'], idx),
                'ifOutErrors': get_interface_oid(INTERFACE_OIDS['ifOutErrors'], idx),
            }

            # Query all OIDs for this interface
            results = self.snmp_get_multiple(device, oids)

            # Convert status values
            admin_status_val = results.get('ifAdminStatus')
            oper_status_val = results.get('ifOperStatus')

            try:
                admin_status = get_status_name(int(admin_status_val), 'admin') if admin_status_val else 'unknown'
            except (ValueError, TypeError):
                admin_status = 'unknown'

            try:
                oper_status = get_status_name(int(oper_status_val), 'oper') if oper_status_val else 'unknown'
            except (ValueError, TypeError):
                oper_status = 'unknown'

            # Format MAC address
            mac_address = self._format_mac_address(results.get('ifPhysAddress'))

            # Build interface stats dict
            stats = {
                'index': idx,
                'name': str(results.get('ifDescr', iface.get('name', 'N/A'))),
                'type': int(results.get('ifType', 0)) if results.get('ifType') else 0,
                'admin_status': admin_status,
                'oper_status': oper_status,
                'speed': int(results.get('ifSpeed', 0)) if results.get('ifSpeed') else 0,
                'mtu': int(results.get('ifMtu', 0)) if results.get('ifMtu') else 0,
                'mac_address': mac_address,
                'in_octets': int(results.get('ifInOctets', 0)) if results.get('ifInOctets') else 0,
                'in_packets': int(results.get('ifInUcastPkts', 0)) if results.get('ifInUcastPkts') else 0,
                'in_errors': int(results.get('ifInErrors', 0)) if results.get('ifInErrors') else 0,
                'out_octets': int(results.get('ifOutOctets', 0)) if results.get('ifOutOctets') else 0,
                'out_packets': int(results.get('ifOutUcastPkts', 0)) if results.get('ifOutUcastPkts') else 0,
                'out_errors': int(results.get('ifOutErrors', 0)) if results.get('ifOutErrors') else 0,
                'timestamp': timestamp
            }

            interface_stats.append(stats)

        self.logger.info(f"{device_name}: Collected stats for {len(interface_stats)} interfaces")
        return interface_stats

    def collect_device_metrics(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """
        Collect all metrics for a device.

        Combines system information and interface statistics into a single
        result dictionary.

        Args:
            device: Device dictionary from inventory

        Returns:
            Dictionary containing:
                - device_name: Device name
                - ip: Device IP address
                - system_info: System information dict
                - interfaces: List of interface statistics
                - collection_time: Timestamp
                - success: Overall success status
                - error: Error message if failed

        Example:
            metrics = monitor.collect_device_metrics(device)
            if metrics['success']:
                print(f"Device: {metrics['device_name']}")
                print(f"System: {metrics['system_info']['sysDescr']}")
                print(f"Interfaces: {len(metrics['interfaces'])}")
        """
        device_name = device.get('name', 'unknown')
        ip = device.get('ip', 'unknown')
        collection_time = get_human_timestamp()

        self.logger.info(f"Collecting metrics from {device_name} ({ip})")

        try:
            # Collect system info
            system_info = self.get_system_info(device)

            # Collect interface stats
            interfaces = self.get_interface_stats(device)

            # Build result
            result = {
                'device_name': device_name,
                'ip': ip,
                'system_info': system_info,
                'interfaces': interfaces,
                'collection_time': collection_time,
                'success': system_info.get('success', False) or len(interfaces) > 0,
                'error': None
            }

            if result['success']:
                self.logger.info(
                    f"{device_name}: Metrics collected successfully - "
                    f"{len(interfaces)} interfaces"
                )
            else:
                result['error'] = 'Failed to collect any metrics'
                self.logger.warning(f"{device_name}: {result['error']}")

            return result

        except Exception as e:
            error_msg = f"Exception collecting metrics: {str(e)}"
            self.logger.error(f"{device_name}: {error_msg}")
            return {
                'device_name': device_name,
                'ip': ip,
                'system_info': {},
                'interfaces': [],
                'collection_time': collection_time,
                'success': False,
                'error': error_msg
            }

    def collect_multiple_devices(
        self,
        devices: List[Dict[str, Any]],
        parallel: bool = True,
        max_workers: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Collect metrics from multiple devices.

        Can run in parallel (using ThreadPoolExecutor) or sequentially.
        Shows progress indicator during collection.

        Args:
            devices: List of device dictionaries
            parallel: Enable parallel collection (default: True)
            max_workers: Maximum number of parallel workers (default: 5)

        Returns:
            List of metric dictionaries, one per device

        Example:
            devices = inventory.get_devices_by_role('spine')
            results = monitor.collect_multiple_devices(
                devices,
                parallel=True,
                max_workers=3
            )
        """
        if not devices:
            self.logger.warning("No devices provided for collection")
            return []

        self.logger.info(
            f"Collecting metrics from {len(devices)} devices "
            f"({'parallel' if parallel else 'sequential'})"
        )

        results = []

        if parallel and len(devices) > 1:
            # Parallel collection
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_device = {
                    executor.submit(self.collect_device_metrics, device): device
                    for device in devices
                }

                # Process completed tasks with progress bar
                for future in create_progress_bar(
                    as_completed(future_to_device),
                    description="Collecting metrics",
                    total=len(devices)
                ):
                    device = future_to_device[future]
                    device_name = device.get('name', device.get('ip', 'unknown'))

                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        self.logger.error(f"{device_name}: Exception in worker: {e}")
                        results.append({
                            'device_name': device_name,
                            'ip': device.get('ip', 'unknown'),
                            'success': False,
                            'error': str(e),
                            'collection_time': get_human_timestamp()
                        })
        else:
            # Sequential collection
            for device in create_progress_bar(devices, description="Collecting metrics"):
                result = self.collect_device_metrics(device)
                results.append(result)

        # Log summary
        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful
        self.logger.info(
            f"Collection complete - Success: {successful}, Failed: {failed}, "
            f"Total: {len(results)}"
        )

        return results

    def collect_all_devices(self, parallel: bool = True) -> List[Dict[str, Any]]:
        """
        Collect metrics from all SNMP-enabled devices in inventory.

        Automatically filters devices where snmp_enabled=True.

        Args:
            parallel: Enable parallel collection (default: True)

        Returns:
            List of metric dictionaries

        Example:
            all_metrics = monitor.collect_all_devices(parallel=True)
            for metrics in all_metrics:
                if metrics['success']:
                    print(f"{metrics['device_name']}: OK")
                else:
                    print(f"{metrics['device_name']}: FAILED - {metrics['error']}")
        """
        devices = self.inventory_loader.get_snmp_enabled_devices()

        if not devices:
            self.logger.warning("No SNMP-enabled devices found in inventory")
            return []

        self.logger.info(f"Collecting metrics from {len(devices)} SNMP-enabled devices")

        return self.collect_multiple_devices(devices, parallel=parallel)

    def collect_devices_by_role(
        self,
        role: str,
        parallel: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Collect metrics from devices with specific role.

        Filters by both role and SNMP enabled status.

        Args:
            role: Device role (e.g., 'spine', 'leaf', 'border')
            parallel: Enable parallel collection (default: True)

        Returns:
            List of metric dictionaries

        Example:
            spine_metrics = monitor.collect_devices_by_role('spine', parallel=True)
            print(f"Collected metrics from {len(spine_metrics)} spine switches")
        """
        # Get devices by role
        role_devices = self.inventory_loader.get_devices_by_role(role)

        # Filter for SNMP-enabled only
        devices = [d for d in role_devices if d.get('snmp_enabled', False)]

        if not devices:
            self.logger.warning(f"No SNMP-enabled devices found with role '{role}'")
            return []

        self.logger.info(
            f"Collecting metrics from {len(devices)} SNMP-enabled {role} devices"
        )

        return self.collect_multiple_devices(devices, parallel=parallel)


# ============================================================================
# MODULE TESTING AND EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    """
    Example usage and testing of SNMPMonitor class.
    Run this script directly to test SNMP monitoring functionality.
    """
    import sys
    from src.utils import setup_logging, print_separator, print_success, print_error, print_info

    # Setup logging
    logger = setup_logging(log_level="INFO")

    print_separator()
    print("SNMP Monitor - Example Usage")
    print_separator()

    try:
        # Initialize monitor
        print_info("Initializing SNMP Monitor...")
        monitor = SNMPMonitor(
            inventory_path="inventory/devices.yaml",
            default_community="public",
            timeout=5,
            retries=2
        )

        # Get SNMP-enabled devices
        devices = monitor.inventory_loader.get_snmp_enabled_devices()
        print_info(f"Found {len(devices)} SNMP-enabled devices")

        if not devices:
            print_error("No SNMP-enabled devices found in inventory")
            print_info("Please ensure devices have 'snmp_enabled: true' in inventory")
            sys.exit(1)

        # Example 1: Collect from first device
        print_separator()
        print_info("Example 1: Single Device Collection")
        print_separator()

        device = devices[0]
        print(f"Target device: {device['name']} ({device['ip']})")

        # Get system info
        print("\n[System Information]")
        sys_info = monitor.get_system_info(device)
        if sys_info['success']:
            print(f"  Name: {sys_info['sysName']}")
            print(f"  Description: {sys_info['sysDescr'][:60]}...")
            print(f"  Uptime: {sys_info['sysUpTime_readable']}")
            print(f"  Location: {sys_info['sysLocation']}")
            print(f"  Contact: {sys_info['sysContact']}")
        else:
            print_error(f"  Failed: {sys_info['error']}")

        # Get interface stats
        print("\n[Interface Statistics]")
        interfaces = monitor.get_interface_stats(device)
        if interfaces:
            print(f"  Found {len(interfaces)} interfaces")
            for iface in interfaces[:5]:  # Show first 5
                print(f"    {iface['name']}: {iface['oper_status']} "
                      f"(Admin: {iface['admin_status']}, Speed: {iface['speed']} bps)")
            if len(interfaces) > 5:
                print(f"    ... and {len(interfaces) - 5} more interfaces")
        else:
            print_error("  No interfaces found")

        # Example 2: Collect from all devices
        print_separator()
        print_info("Example 2: Multi-Device Collection (Sequential)")
        print_separator()

        results = monitor.collect_multiple_devices(devices[:2], parallel=False)
        print("\nResults:")
        for result in results:
            if result['success']:
                print_success(
                    f"{result['device_name']}: "
                    f"{len(result.get('interfaces', []))} interfaces"
                )
            else:
                print_error(f"{result['device_name']}: {result.get('error', 'Unknown error')}")

        # Example 3: Collect by role (if spine devices exist)
        print_separator()
        print_info("Example 3: Collection by Role")
        print_separator()

        spine_results = monitor.collect_devices_by_role('spine', parallel=True)
        if spine_results:
            print(f"Collected from {len(spine_results)} spine devices")
            for result in spine_results:
                if result['success']:
                    uptime = result.get('system_info', {}).get('sysUpTime_readable', 'N/A')
                    print_success(f"{result['device_name']}: Uptime={uptime}")
        else:
            print_info("No spine devices found or collection failed")

        print_separator()
        print_success("All examples completed!")
        print_separator()

    except FileNotFoundError as e:
        print_error(f"Inventory file not found: {e}")
        print_info("Make sure inventory/devices.yaml exists")
        sys.exit(1)

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
