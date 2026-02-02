import logging
import time
from typing import Optional, Union, List
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
    SSHException,
)

from exceptions import (
    ConnectionError,
    AuthenticationError,
    TimeoutError,
    CommandExecutionError,
    DeviceNotReachableError,
)


# Configure logging
logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages SSH connections to network devices using Netmiko.

    This class provides a robust interface for establishing and managing SSH
    connections to network devices with automatic retry logic, comprehensive
    error handling, and context manager support for automatic cleanup.

    Attributes:
        device (dict): Device information dictionary containing connection details
        connection: Netmiko ConnectHandler instance or None
        max_retries (int): Maximum number of connection retry attempts
        retry_delay (int): Initial delay between retries in seconds
    """

    def __init__(
        self,
        device: dict,
        max_retries: int = 3,
        retry_delay: int = 2
    ):
        """
        Initialize ConnectionManager.

        Args:
            device: Dictionary containing device connection information
            max_retries: Maximum number of connection attempts (default: 3)
            retry_delay: Initial delay between retries in seconds (default: 2)
        """
        self.device = device
        self.connection: Optional[ConnectHandler] = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.device_name = device.get("name", device.get("ip", "unknown"))

        logger.debug(
            f"ConnectionManager initialized for device '{self.device_name}' "
            f"(max_retries={max_retries}, retry_delay={retry_delay})"
        )

    def connect(self) -> bool:
        """
        Establish SSH connection to the device with retry logic.

        Attempts to connect to the device using the provided credentials.
        Implements exponential backoff retry strategy for transient failures.
        Converts Netmiko exceptions to custom exceptions for consistent
        error handling.

        Returns:
            bool: True if connection successful
        """
        device_info = {
            "device_type": self.device.get("device_type", "nokia_sros"),
            "host": self.device["ip"],
            "username": self.device["username"],
            "password": self.device["password"],
            "timeout": self.device.get("timeout", 10),
            "session_log": None,  # Can be configured for debugging
        }

        attempt = 0
        last_exception = None

        while attempt < self.max_retries:
            attempt += 1
            delay = self.retry_delay * (2 ** (attempt - 1))  # Exponential backoff

            try:
                logger.info(
                    f"Attempting to connect to device '{self.device_name}' "
                    f"({self.device['ip']}) - Attempt {attempt}/{self.max_retries}"
                )

                self.connection = ConnectHandler(**device_info)

                logger.info(
                    f"Successfully connected to device '{self.device_name}' "
                    f"({self.device['ip']})"
                )
                return True

            except NetmikoAuthenticationException as e:
                logger.error(
                    f"Authentication failed for device '{self.device_name}': {e}"
                )
                raise AuthenticationError(
                    f"Authentication failed: {str(e)}",
                    device_name=self.device_name
                )

            except NetmikoTimeoutException as e:
                last_exception = e
                logger.warning(
                    f"Connection timeout for device '{self.device_name}' "
                    f"on attempt {attempt}/{self.max_retries}: {e}"
                )

                if attempt < self.max_retries:
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Device '{self.device_name}' not reachable after "
                        f"{self.max_retries} attempts"
                    )
                    raise DeviceNotReachableError(
                        f"Device not reachable after {self.max_retries} attempts: {str(e)}",
                        device_name=self.device_name
                    )

            except SSHException as e:
                last_exception = e
                logger.warning(
                    f"SSH error for device '{self.device_name}' "
                    f"on attempt {attempt}/{self.max_retries}: {e}"
                )

                if attempt < self.max_retries:
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Failed to connect to device '{self.device_name}' after "
                        f"{self.max_retries} attempts"
                    )
                    raise ConnectionError(
                        f"SSH connection failed after {self.max_retries} attempts: {str(e)}",
                        device_name=self.device_name
                    )

            except Exception as e:
                logger.error(
                    f"Unexpected error connecting to device '{self.device_name}': {e}"
                )
                raise ConnectionError(
                    f"Unexpected connection error: {str(e)}",
                    device_name=self.device_name
                )

        # Should not reach here, but just in case
        raise ConnectionError(
            f"Failed to connect after {self.max_retries} attempts",
            device_name=self.device_name
        )

    def disconnect(self) -> None:
        """
        Safely close the SSH connection.

        Closes the connection if one exists and handles any errors gracefully.
        Sets the connection attribute to None after disconnection.
        """
        if self.connection:
            try:
                logger.info(f"Disconnecting from device '{self.device_name}'")
                self.connection.disconnect()
                logger.info(f"Successfully disconnected from device '{self.device_name}'")
            except Exception as e:
                logger.warning(
                    f"Error while disconnecting from device '{self.device_name}': {e}"
                )
            finally:
                self.connection = None
        else:
            logger.debug(f"No active connection to device '{self.device_name}' to disconnect")

    def is_connected(self) -> bool:
        """
        Check if connection is active.

        Returns:
            bool: True if connected, False otherwise
        """
        if self.connection is None:
            return False

        try:
            # Try to check if connection is alive
            return self.connection.is_alive()
        except Exception:
            return False

    def send_command(
        self,
        command: str,
        expect_string: Optional[str] = None
    ) -> str:
        """
        Send a command to the device and return output.

        Args:
            command: Command string to execute
            expect_string: Optional string to expect in output (for prompts)

        Returns:
            str: Command output
        """
        if not self.is_connected():
            logger.error(
                f"Cannot send command to device '{self.device_name}': Not connected"
            )
            raise ConnectionError(
                "Not connected to device. Call connect() first.",
                device_name=self.device_name
            )

        try:
            logger.debug(f"Sending command to device '{self.device_name}': {command}")

            if expect_string:
                output = self.connection.send_command(
                    command,
                    expect_string=expect_string
                )
            else:
                output = self.connection.send_command(command)

            logger.debug(
                f"Command executed successfully on device '{self.device_name}'"
            )
            return output

        except Exception as e:
            logger.error(
                f"Command execution failed on device '{self.device_name}': {e}"
            )
            raise CommandExecutionError(
                f"Failed to execute command '{command}': {str(e)}",
                device_name=self.device_name
            )

    def send_config(self, commands: Union[str, List[str]]) -> str:
        """
        Send configuration commands to the device.

        Enters configuration mode, sends the configuration commands,
        and returns the output.

        Args:
            commands: Single command string or list of command strings

        Returns:
            str: Configuration output
        """
        if not self.is_connected():
            logger.error(
                f"Cannot send config to device '{self.device_name}': Not connected"
            )
            raise ConnectionError(
                "Not connected to device. Call connect() first.",
                device_name=self.device_name
            )

        try:
            logger.debug(
                f"Sending configuration to device '{self.device_name}': {commands}"
            )

            output = self.connection.send_config_set(commands)

            logger.info(
                f"Configuration applied successfully on device '{self.device_name}'"
            )
            return output

        except Exception as e:
            logger.error(
                f"Configuration failed on device '{self.device_name}': {e}"
            )
            raise CommandExecutionError(
                f"Failed to apply configuration: {str(e)}",
                device_name=self.device_name
            )

    def __enter__(self):
        """
        Context manager entry point.

        Establishes connection when entering the context.

        Returns:
            ConnectionManager: self
        """
        logger.debug(f"Entering context manager for device '{self.device_name}'")
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point.

        Safely disconnects when exiting the context, regardless of whether
        an exception occurred.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        Returns:
            bool: False to propagate any exception that occurred
        """
        logger.debug(f"Exiting context manager for device '{self.device_name}'")
        self.disconnect()
        return False  # Don't suppress exceptions

    def __repr__(self) -> str:
        """Return string representation of ConnectionManager."""
        status = "connected" if self.is_connected() else "disconnected"
        return (
            f"ConnectionManager(device='{self.device_name}', "
            f"ip='{self.device.get('ip')}', status='{status}')"
        )
