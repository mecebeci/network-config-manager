class ConnectionError(Exception):
    """
    Exception raised when SSH connection to a network device fails.

    Use this exception when:
    - Unable to establish TCP connection to the device
    - Connection is refused or dropped
    - Network connectivity issues prevent connection

    Attributes:
        message (str): Description of the connection error
        device_name (str): Name or identifier of the device (optional)

    Example:
        raise ConnectionError("Failed to connect to device", device_name="spine1")
    """

    def __init__(self, message: str, device_name: str = None):
        """
        Initialize ConnectionError.

        Args:
            message: Description of the connection error
            device_name: Name or identifier of the device (optional)
        """
        self.message = message
        self.device_name = device_name
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.device_name:
            return f"ConnectionError for device '{self.device_name}': {self.message}"
        return f"ConnectionError: {self.message}"


class AuthenticationError(Exception):
    """
    Exception raised when authentication to a network device fails.

    Use this exception when:
    - Invalid credentials (username/password)
    - SSH key authentication fails
    - Insufficient privileges for the operation
    - Authentication method not supported

    Attributes:
        message (str): Description of the authentication error
        device_name (str): Name or identifier of the device (optional)

    Example:
        raise AuthenticationError("Invalid credentials", device_name="leaf1")
    """

    def __init__(self, message: str, device_name: str = None):
        """
        Initialize AuthenticationError.

        Args:
            message: Description of the authentication error
            device_name: Name or identifier of the device (optional)
        """
        self.message = message
        self.device_name = device_name
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.device_name:
            return f"AuthenticationError for device '{self.device_name}': {self.message}"
        return f"AuthenticationError: {self.message}"


class TimeoutError(Exception):
    """
    Exception raised when connection or command execution times out.

    Use this exception when:
    - Connection attempt exceeds timeout threshold
    - Command execution takes too long
    - Device is not responding within expected time

    Attributes:
        message (str): Description of the timeout error
        device_name (str): Name or identifier of the device (optional)

    Example:
        raise TimeoutError("Connection timeout after 30 seconds", device_name="spine1")
    """

    def __init__(self, message: str, device_name: str = None):
        """
        Initialize TimeoutError.

        Args:
            message: Description of the timeout error
            device_name: Name or identifier of the device (optional)
        """
        self.message = message
        self.device_name = device_name
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.device_name:
            return f"TimeoutError for device '{self.device_name}': {self.message}"
        return f"TimeoutError: {self.message}"


class CommandExecutionError(Exception):
    """
    Exception raised when command execution on a device fails.

    Use this exception when:
    - Command returns an error message
    - Invalid command syntax
    - Command not supported on device
    - Command execution interrupted

    Attributes:
        message (str): Description of the command execution error
        device_name (str): Name or identifier of the device (optional)

    Example:
        raise CommandExecutionError("Invalid command syntax", device_name="leaf2")
    """

    def __init__(self, message: str, device_name: str = None):
        """
        Initialize CommandExecutionError.

        Args:
            message: Description of the command execution error
            device_name: Name or identifier of the device (optional)
        """
        self.message = message
        self.device_name = device_name
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.device_name:
            return f"CommandExecutionError for device '{self.device_name}': {self.message}"
        return f"CommandExecutionError: {self.message}"


class DeviceNotReachableError(Exception):
    """
    Exception raised when a network device is not reachable.

    Use this exception when:
    - Device does not respond to ping or connection attempts
    - Device is powered off or disconnected
    - Network path to device is broken
    - Device IP address is incorrect or not routable

    Attributes:
        message (str): Description of the reachability error
        device_name (str): Name or identifier of the device (optional)

    Example:
        raise DeviceNotReachableError("Device not responding", device_name="spine1")
    """

    def __init__(self, message: str, device_name: str = None):
        """
        Initialize DeviceNotReachableError.

        Args:
            message: Description of the reachability error
            device_name: Name or identifier of the device (optional)
        """
        self.message = message
        self.device_name = device_name
        super().__init__(self.message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.device_name:
            return f"DeviceNotReachableError for device '{self.device_name}': {self.message}"
        return f"DeviceNotReachableError: {self.message}"
