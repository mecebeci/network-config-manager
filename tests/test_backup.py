"""Tests for backup module."""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.backup import ConfigBackup
from src.exceptions import ConnectionError, DeviceNotReachableError


@pytest.mark.unit
class TestConfigBackup:
    """Test cases for ConfigBackup class."""

    def test_init(self, test_inventory_file, temp_dir):
        """Test ConfigBackup initialization."""
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        assert backup_mgr.backup_dir == temp_dir
        assert backup_mgr.retention_days == 30

    def test_init_custom_retention(self, test_inventory_file, temp_dir):
        """Test initialization with custom retention."""
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir,
            retention_days=60
        )
        assert backup_mgr.retention_days == 60

    def test_init_invalid_inventory(self, temp_dir):
        """Test initialization with invalid inventory path."""
        with pytest.raises(Exception):
            ConfigBackup(
                inventory_path="/nonexistent/inventory.yaml",
                backup_dir=temp_dir
            )

    @patch('src.backup.ConnectionManager')
    def test_backup_device_success(self, mock_conn_mgr_class, mock_device, temp_dir, test_inventory_file):
        """Test successful device backup."""
        # Mock connection and command output
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_command.return_value = "! Test config\nhostname test_device1"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        result = backup_mgr.backup_device(mock_device)

        assert result['success'] is True
        assert result['device_name'] == 'test_device1'
        assert result['filepath'] is not None
        assert os.path.exists(result['filepath'])

    @patch('src.backup.ConnectionManager')
    def test_backup_device_connection_failure(self, mock_conn_mgr_class, mock_device, temp_dir, test_inventory_file):
        """Test backup with connection failure."""
        # Mock connection failure
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.side_effect = ConnectionError("Connection failed", device_name="test_device1")
        mock_conn_mgr_class.return_value = mock_conn_mgr

        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        result = backup_mgr.backup_device(mock_device)

        assert result['success'] is False
        assert 'error' in result

    def test_get_latest_backup(self, test_backup_file, temp_dir, test_inventory_file):
        """Test getting latest backup."""
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        latest = backup_mgr.get_latest_backup('test_device1')
        assert latest is not None
        assert 'test_device1' in latest

    def test_get_latest_backup_no_backups(self, temp_dir, test_inventory_file):
        """Test getting latest backup when none exist."""
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        latest = backup_mgr.get_latest_backup('nonexistent_device')
        assert latest is None

    def test_list_device_backups(self, test_backup_file, temp_dir, test_inventory_file):
        """Test listing device backups."""
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        backups = backup_mgr.list_device_backups('test_device1')
        assert len(backups) > 0
        assert all('test_device1' in b for b in backups)

    def test_list_device_backups_empty(self, temp_dir, test_inventory_file):
        """Test listing backups for device with no backups."""
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        backups = backup_mgr.list_device_backups('nonexistent_device')
        assert len(backups) == 0

    @patch('src.backup.ConnectionManager')
    def test_backup_all_devices(self, mock_conn_mgr_class, temp_dir, test_inventory_file):
        """Test backing up all devices."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_command.return_value = "! Test config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        results = backup_mgr.backup_all_devices(parallel=False)

        assert isinstance(results, list)
        assert len(results) == 2  # test_inventory has 2 devices
        assert all('device_name' in r for r in results)

    @patch('src.backup.ConnectionManager')
    def test_backup_devices_by_role(self, mock_conn_mgr_class, temp_dir, test_inventory_file):
        """Test backing up devices by role."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_command.return_value = "! Test config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        results = backup_mgr.backup_devices_by_role('spine', parallel=False)

        assert isinstance(results, list)
        assert len(results) == 1  # Only one spine device

    def test_cleanup_old_backups(self, temp_dir, test_inventory_file):
        """Test cleanup of old backups."""
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir,
            retention_days=1
        )
        # This should clean up old backups
        result = backup_mgr.cleanup_old_backups()
        assert isinstance(result, dict)
        assert 'deleted_count' in result
        assert result['deleted_count'] >= 0
