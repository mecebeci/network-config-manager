"""Tests for connection_manager module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException,
    SSHException
)
from src.connection_manager import ConnectionManager
from src.exceptions import (
    ConnectionError,
    AuthenticationError,
    DeviceNotReachableError
)


@pytest.mark.unit
class TestConnectionManager:
    """Test cases for ConnectionManager class."""

    def test_init(self, mock_device):
        """Test ConnectionManager initialization."""
        conn_mgr = ConnectionManager(mock_device)
        assert conn_mgr.device == mock_device
        assert conn_mgr.connection is None
        assert conn_mgr.max_retries == 3
        assert conn_mgr.device_name == 'test_device1'

    def test_init_with_custom_retries(self, mock_device):
        """Test initialization with custom retry settings."""
        conn_mgr = ConnectionManager(mock_device, max_retries=5, retry_delay=1)
        assert conn_mgr.max_retries == 5
        assert conn_mgr.retry_delay == 1

    @patch('src.connection_manager.ConnectHandler')
    def test_connect_success(self, mock_connect_handler, mock_device):
        """Test successful connection."""
        mock_connection = MagicMock()
        mock_connect_handler.return_value = mock_connection

        conn_mgr = ConnectionManager(mock_device)
        result = conn_mgr.connect()

        assert result is True
        assert conn_mgr.connection is not None
        mock_connect_handler.assert_called_once()

    @patch('src.connection_manager.ConnectHandler')
    def test_connect_authentication_failure(self, mock_connect_handler, mock_device):
        """Test connection with authentication failure."""
        mock_connect_handler.side_effect = NetmikoAuthenticationException("Auth failed")

        conn_mgr = ConnectionManager(mock_device, max_retries=1)

        with pytest.raises(AuthenticationError):
            conn_mgr.connect()

    @patch('src.connection_manager.ConnectHandler')
    @patch('src.connection_manager.time.sleep')
    def test_connect_timeout_failure(self, mock_sleep, mock_connect_handler, mock_device):
        """Test connection with timeout failure."""
        mock_connect_handler.side_effect = NetmikoTimeoutException("Connection timeout")

        conn_mgr = ConnectionManager(mock_device, max_retries=2, retry_delay=1)

        with pytest.raises(DeviceNotReachableError):
            conn_mgr.connect()

        # Should have tried max_retries times
        assert mock_connect_handler.call_count == 2

    @patch('src.connection_manager.ConnectHandler')
    @patch('src.connection_manager.time.sleep')
    def test_connect_ssh_exception(self, mock_sleep, mock_connect_handler, mock_device):
        """Test connection with SSH exception."""
        mock_connect_handler.side_effect = SSHException("SSH error")

        conn_mgr = ConnectionManager(mock_device, max_retries=2, retry_delay=1)

        with pytest.raises(ConnectionError):
            conn_mgr.connect()

        # Should have tried max_retries times
        assert mock_connect_handler.call_count == 2

    @patch('src.connection_manager.ConnectHandler')
    @patch('src.connection_manager.time.sleep')
    def test_connect_retry_success(self, mock_sleep, mock_connect_handler, mock_device):
        """Test connection succeeds on retry."""
        mock_connection = MagicMock()
        # Fail first attempt, succeed on second
        mock_connect_handler.side_effect = [
            NetmikoTimeoutException("Timeout"),
            mock_connection
        ]

        conn_mgr = ConnectionManager(mock_device, max_retries=3, retry_delay=1)
        result = conn_mgr.connect()

        assert result is True
        assert conn_mgr.connection is not None
        assert mock_connect_handler.call_count == 2

    def test_disconnect(self, mock_device):
        """Test disconnect."""
        conn_mgr = ConnectionManager(mock_device)
        mock_connection = MagicMock()
        conn_mgr.connection = mock_connection
        conn_mgr.disconnect()
        mock_connection.disconnect.assert_called_once()
        assert conn_mgr.connection is None

    def test_disconnect_no_connection(self, mock_device):
        """Test disconnect when no connection exists."""
        conn_mgr = ConnectionManager(mock_device)
        # Should not raise an error
        conn_mgr.disconnect()
        assert conn_mgr.connection is None

    @patch('src.connection_manager.ConnectHandler')
    def test_is_connected(self, mock_connect_handler, mock_device):
        """Test is_connected method."""
        mock_connection = MagicMock()
        mock_connection.is_alive.return_value = True
        mock_connect_handler.return_value = mock_connection

        conn_mgr = ConnectionManager(mock_device)
        conn_mgr.connect()

        assert conn_mgr.is_connected() is True

    def test_is_connected_no_connection(self, mock_device):
        """Test is_connected when no connection exists."""
        conn_mgr = ConnectionManager(mock_device)
        assert conn_mgr.is_connected() is False

    @patch('src.connection_manager.ConnectHandler')
    def test_context_manager(self, mock_connect_handler, mock_device):
        """Test context manager protocol."""
        mock_connection = MagicMock()
        mock_connect_handler.return_value = mock_connection

        with ConnectionManager(mock_device) as conn_mgr:
            assert conn_mgr.connection is not None

        # Connection should be closed after context
        mock_connection.disconnect.assert_called()

    @patch('src.connection_manager.ConnectHandler')
    def test_send_command(self, mock_connect_handler, mock_device):
        """Test sending command to device."""
        mock_connection = MagicMock()
        mock_connection.send_command.return_value = "Command output"
        mock_connect_handler.return_value = mock_connection

        conn_mgr = ConnectionManager(mock_device)
        conn_mgr.connect()
        result = conn_mgr.send_command("show version")

        assert result == "Command output"
        mock_connection.send_command.assert_called_once_with("show version")

    @patch('src.connection_manager.ConnectHandler')
    def test_send_config(self, mock_connect_handler, mock_device):
        """Test sending configuration commands."""
        mock_connection = MagicMock()
        mock_connection.send_config_set.return_value = "Config output"
        mock_connect_handler.return_value = mock_connection

        conn_mgr = ConnectionManager(mock_device)
        conn_mgr.connect()
        commands = ["interface ethernet-1/1", "admin-state enable"]
        result = conn_mgr.send_config(commands)

        assert result == "Config output"
        mock_connection.send_config_set.assert_called_once_with(commands)
