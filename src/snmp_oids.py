"""
SNMP OID Definitions for Network Monitoring

This module provides a centralized repository of SNMP Object Identifiers (OIDs)
used for monitoring network devices. It includes OIDs for system information,
interface statistics, traffic data, and device health metrics.

OID Categories:
- SYSTEM_OIDS: Basic system information (description, uptime, location, etc.)
- INTERFACE_OIDS: Interface statistics from the IF-MIB (ifTable)
- INTERFACE_INDEX_OID: Base OID for interface indexing
- Status mappings: Human-readable status values

Usage:
    from snmp_oids import SYSTEM_OIDS, INTERFACE_OIDS, ADMIN_STATUS

    # Get system description OID
    sys_descr_oid = SYSTEM_OIDS['sysDescr']

    # Get interface description OID for walking
    if_descr_base = INTERFACE_OIDS['ifDescr']

    # Translate admin status value
    status = ADMIN_STATUS.get(1, 'unknown')  # Returns 'up'
"""

# ============================================================================
# A. SYSTEM OIDS (RFC 1213 - MIB-II System Group)
# ============================================================================

SYSTEM_OIDS = {
    'sysDescr': '1.3.6.1.2.1.1.1.0',        # System description
    'sysObjectID': '1.3.6.1.2.1.1.2.0',     # System object ID
    'sysUpTime': '1.3.6.1.2.1.1.3.0',       # System uptime (timeticks)
    'sysContact': '1.3.6.1.2.1.1.4.0',      # System contact
    'sysName': '1.3.6.1.2.1.1.5.0',         # System name
    'sysLocation': '1.3.6.1.2.1.1.6.0',     # System location
}

"""
System OID Descriptions:
- sysDescr: Full description of the system including hardware and OS version
- sysObjectID: Vendor's authoritative identification of the network management subsystem
- sysUpTime: Time since the network management portion of the system was last re-initialized (in hundredths of seconds)
- sysContact: Contact person for this managed node
- sysName: Administratively assigned name for this managed node
- sysLocation: Physical location of this node
"""


# ============================================================================
# B. INTERFACE OIDS (RFC 1213 - MIB-II Interfaces Group - ifTable)
# ============================================================================

INTERFACE_OIDS = {
    'ifDescr': '1.3.6.1.2.1.2.2.1.2',       # Interface description
    'ifType': '1.3.6.1.2.1.2.2.1.3',        # Interface type
    'ifMtu': '1.3.6.1.2.1.2.2.1.4',         # Interface MTU
    'ifSpeed': '1.3.6.1.2.1.2.2.1.5',       # Interface speed
    'ifPhysAddress': '1.3.6.1.2.1.2.2.1.6', # MAC address
    'ifAdminStatus': '1.3.6.1.2.1.2.2.1.7', # Admin status (1=up, 2=down, 3=testing)
    'ifOperStatus': '1.3.6.1.2.1.2.2.1.8',  # Operational status (1=up, 2=down, 3=testing, 4=unknown, 5=dormant, 6=notPresent, 7=lowerLayerDown)
    'ifInOctets': '1.3.6.1.2.1.2.2.1.10',   # Incoming bytes
    'ifInUcastPkts': '1.3.6.1.2.1.2.2.1.11', # Incoming unicast packets
    'ifInErrors': '1.3.6.1.2.1.2.2.1.14',   # Incoming errors
    'ifOutOctets': '1.3.6.1.2.1.2.2.1.16',  # Outgoing bytes
    'ifOutUcastPkts': '1.3.6.1.2.1.2.2.1.17', # Outgoing unicast packets
    'ifOutErrors': '1.3.6.1.2.1.2.2.1.20',  # Outgoing errors
}

"""
Interface OID Descriptions:
- ifDescr: Textual description of the interface (e.g., "GigabitEthernet0/1")
- ifType: Type of interface (e.g., 6=ethernetCsmacd, 24=softwareLoopback)
- ifMtu: Maximum Transfer Unit size in octets
- ifSpeed: Estimate of interface's current bandwidth in bits per second
- ifPhysAddress: Interface's MAC address
- ifAdminStatus: Desired state of the interface (administratively configured)
- ifOperStatus: Current operational state of the interface
- ifInOctets: Total bytes received on the interface (counter32)
- ifInUcastPkts: Number of unicast packets delivered to higher layer
- ifInErrors: Number of inbound packets with errors
- ifOutOctets: Total bytes transmitted from the interface (counter32)
- ifOutUcastPkts: Total unicast packets transmitted
- ifOutErrors: Number of outbound packets with errors
"""


# ============================================================================
# C. INTERFACE INDEX OID
# ============================================================================

INTERFACE_INDEX_OID = '1.3.6.1.2.1.2.2.1.1'  # ifIndex

"""
Interface Index OID:
- ifIndex: Unique value identifying each interface. Used as the index for
  accessing other interface-specific OIDs. For example, to get the description
  of interface 1, you would query: 1.3.6.1.2.1.2.2.1.2.1
"""


# ============================================================================
# D. STATUS MAPPINGS
# ============================================================================

ADMIN_STATUS = {
    1: 'up',
    2: 'down',
    3: 'testing'
}

"""
Administrative Status Values:
- up(1): Interface is administratively enabled and ready to pass packets
- down(2): Interface is administratively disabled
- testing(3): Interface is in testing mode
"""

OPER_STATUS = {
    1: 'up',
    2: 'down',
    3: 'testing',
    4: 'unknown',
    5: 'dormant',
    6: 'notPresent',
    7: 'lowerLayerDown'
}

"""
Operational Status Values:
- up(1): Interface is ready to pass packets
- down(2): Interface is not operational
- testing(3): Interface is in testing mode (no operational packets passed)
- unknown(4): Status cannot be determined
- dormant(5): Interface is waiting for external actions (e.g., dial-on-demand link)
- notPresent(6): Component is not present (e.g., removed module)
- lowerLayerDown(7): Interface is down due to state of lower-layer interface(s)
"""


# ============================================================================
# E. INTERFACE TYPE MAPPINGS (Common Types)
# ============================================================================

INTERFACE_TYPES = {
    1: 'other',
    6: 'ethernetCsmacd',
    23: 'ppp',
    24: 'softwareLoopback',
    131: 'tunnel',
    135: 'l2vlan',
    136: 'l3ipvlan',
    161: 'ieee8023adLag',
    244: 'wwanPP'
}

"""
Interface Type Values (Common):
- other(1): Other/unknown interface type
- ethernetCsmacd(6): Ethernet interface
- ppp(23): Point-to-Point Protocol
- softwareLoopback(24): Software loopback interface
- tunnel(131): Tunnel interface
- l2vlan(135): Layer 2 VLAN interface
- l3ipvlan(136): Layer 3 IP VLAN interface
- ieee8023adLag(161): Link Aggregation (LAG/Port-Channel)
- wwanPP(244): WWAN interface

Note: This is a subset of the full interface type enumeration.
For complete list, see IANAifType-MIB.
"""


# ============================================================================
# F. UTILITY FUNCTIONS
# ============================================================================

def get_interface_oid(base_oid: str, interface_index: int) -> str:
    """
    Construct a complete interface OID by appending interface index.

    Args:
        base_oid: Base OID from INTERFACE_OIDS (e.g., '1.3.6.1.2.1.2.2.1.2')
        interface_index: Interface index number

    Returns:
        Complete OID string

    Example:
        >>> get_interface_oid(INTERFACE_OIDS['ifDescr'], 1)
        '1.3.6.1.2.1.2.2.1.2.1'
    """
    return f"{base_oid}.{interface_index}"


def parse_interface_index_from_oid(oid: str) -> int:
    """
    Extract interface index from a complete interface OID.

    Args:
        oid: Complete OID string (e.g., '1.3.6.1.2.1.2.2.1.2.1')

    Returns:
        Interface index as integer

    Example:
        >>> parse_interface_index_from_oid('1.3.6.1.2.1.2.2.1.2.1')
        1
    """
    return int(oid.split('.')[-1])


def get_status_name(status_value: int, status_type: str = 'oper') -> str:
    """
    Convert numeric status value to human-readable name.

    Args:
        status_value: Numeric status value from SNMP
        status_type: Type of status ('admin' or 'oper')

    Returns:
        Status name as string (e.g., 'up', 'down')

    Example:
        >>> get_status_name(1, 'admin')
        'up'
        >>> get_status_name(7, 'oper')
        'lowerLayerDown'
    """
    if status_type.lower() == 'admin':
        return ADMIN_STATUS.get(status_value, 'unknown')
    elif status_type.lower() == 'oper':
        return OPER_STATUS.get(status_value, 'unknown')
    else:
        return 'unknown'


def get_interface_type_name(type_value: int) -> str:
    """
    Convert numeric interface type to human-readable name.

    Args:
        type_value: Numeric interface type value from SNMP

    Returns:
        Interface type name as string

    Example:
        >>> get_interface_type_name(6)
        'ethernetCsmacd'
        >>> get_interface_type_name(999)
        'unknown'
    """
    return INTERFACE_TYPES.get(type_value, 'unknown')


# ============================================================================
# MODULE TESTING
# ============================================================================

if __name__ == "__main__":
    """
    Test and demonstrate OID definitions and utility functions.
    """
    print("=" * 80)
    print("SNMP OID Definitions - Demo")
    print("=" * 80)

    # Display System OIDs
    print("\nSYSTEM OIDs:")
    print("-" * 80)
    for name, oid in SYSTEM_OIDS.items():
        print(f"  {name:<20} {oid}")

    # Display Interface OIDs
    print("\nINTERFACE OIDs:")
    print("-" * 80)
    for name, oid in INTERFACE_OIDS.items():
        print(f"  {name:<20} {oid}")

    # Display Status Mappings
    print("\nADMIN STATUS MAPPINGS:")
    print("-" * 80)
    for value, name in ADMIN_STATUS.items():
        print(f"  {value}: {name}")

    print("\nOPER STATUS MAPPINGS:")
    print("-" * 80)
    for value, name in OPER_STATUS.items():
        print(f"  {value}: {name}")

    # Test utility functions
    print("\nUTILITY FUNCTION TESTS:")
    print("-" * 80)

    # Test get_interface_oid
    test_oid = get_interface_oid(INTERFACE_OIDS['ifDescr'], 1)
    print(f"  Interface 1 description OID: {test_oid}")

    # Test parse_interface_index_from_oid
    test_index = parse_interface_index_from_oid('1.3.6.1.2.1.2.2.1.2.5')
    print(f"  Parsed interface index: {test_index}")

    # Test get_status_name
    admin_status = get_status_name(1, 'admin')
    oper_status = get_status_name(7, 'oper')
    print(f"  Admin status 1: {admin_status}")
    print(f"  Oper status 7: {oper_status}")

    # Test get_interface_type_name
    if_type = get_interface_type_name(6)
    print(f"  Interface type 6: {if_type}")

    print("\n" + "=" * 80)
    print("Demo complete!")
    print("=" * 80)
