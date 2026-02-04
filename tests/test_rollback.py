"""Tests for rollback module."""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.rollback import ConfigRollback
from src.exceptions import ConnectionError


@pytest.mark.unit
class TestConfigRollback:
    """Test cases for ConfigRollback class."""

    def test_init(self, test_inventory_file, temp_dir):
        """Test ConfigRollback initialization."""
        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        assert rollback_mgr.backup_dir == temp_dir

    def test_init_invalid_inventory(self, temp_dir):
        """Test initialization with invalid inventory."""
        with pytest.raises(Exception):
            ConfigRollback(
                inventory_path="/nonexistent/inventory.yaml",
                backup_dir=temp_dir
            )

    def test_list_device_backups(self, test_backup_file, temp_dir, test_inventory_file):
        """Test listing device backups."""
        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        backups = rollback_mgr.list_device_backups('test_device1')

        assert isinstance(backups, list)
        assert len(backups) > 0

    def test_list_device_backups_no_backups(self, temp_dir, test_inventory_file):
        """Test listing backups when none exist."""
        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        backups = rollback_mgr.list_device_backups('nonexistent_device')

        assert isinstance(backups, list)
        assert len(backups) == 0

    @patch('src.rollback.ConnectionManager')
    def test_rollback_device_success(self, mock_conn_mgr_class, mock_device, test_backup_file, temp_dir, test_inventory_file):
        """Test successful rollback to backup."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_config_set.return_value = "Config applied"
        mock_conn_mgr.send_command.return_value = "! Current config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        result = rollback_mgr.rollback_device(mock_device, test_backup_file)

        assert result['success'] is True
        assert result['device_name'] == 'test_device1'

    @patch('src.rollback.ConnectionManager')
    def test_rollback_connection_failure(self, mock_conn_mgr_class, mock_device, test_backup_file, temp_dir, test_inventory_file):
        """Test rollback with connection failure."""
        # Mock connection failure
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.side_effect = ConnectionError("Connection failed", device_name="test_device1")
        mock_conn_mgr_class.return_value = mock_conn_mgr

        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        result = rollback_mgr.rollback_device(mock_device, test_backup_file)

        assert result['success'] is False
        assert 'error' in result

    def test_rollback_nonexistent_backup(self, mock_device, temp_dir, test_inventory_file):
        """Test rollback with non-existent backup file."""
        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        result = rollback_mgr.rollback_device(mock_device, '/nonexistent/backup.cfg')

        assert result['success'] is False
        assert 'error' in result

    @patch('src.rollback.ConnectionManager')
    def test_rollback_to_latest_backup(self, mock_conn_mgr_class, mock_device, temp_dir, test_inventory_file):
        """Test rollback to latest backup using get_latest_backup."""
        # Create a backup file manually in the correct location
        import os
        from src.utils import get_timestamp
        backup_filename = f"test_device1_{get_timestamp()}.cfg"
        backup_filepath = os.path.join(temp_dir, backup_filename)
        with open(backup_filepath, 'w') as f:
            f.write("! Test backup configuration\n/interface ethernet-1/1\n    admin-state enable\n")

        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_config_set.return_value = "Config applied"
        mock_conn_mgr.send_command.return_value = "! Current config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        # Get latest backup
        latest_backup = rollback_mgr.get_latest_backup('test_device1')
        assert latest_backup is not None
        assert isinstance(latest_backup, dict)
        assert 'filepath' in latest_backup

        # Rollback to it using the filepath
        result = rollback_mgr.rollback_device(mock_device, latest_backup['filepath'])
        assert result['success'] is True

    def test_rollback_to_latest_no_backups(self, mock_device, temp_dir, test_inventory_file):
        """Test rollback when no backups exist."""
        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        # Use a device with no backups
        device_no_backup = mock_device.copy()
        device_no_backup['name'] = 'nonexistent_device'

        # Get latest backup should return None
        latest_backup = rollback_mgr.get_latest_backup('nonexistent_device')
        assert latest_backup is None

    @patch('src.rollback.ConnectionManager')
    def test_rollback_with_safety_backup(self, mock_conn_mgr_class, mock_device, test_backup_file, temp_dir, test_inventory_file):
        """Test rollback with safety backup before rollback."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_config_set.return_value = "Config applied"
        mock_conn_mgr.send_command.return_value = "! Current config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        result = rollback_mgr.rollback_device(
            mock_device,
            test_backup_file,
            safety_backup=True
        )

        assert result['success'] is True

    def test_get_backup_info(self, test_backup_file, temp_dir, test_inventory_file):
        """Test getting backup information."""
        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        info = rollback_mgr.get_backup_info(test_backup_file)

        assert isinstance(info, dict)
        assert 'filepath' in info
        assert 'size' in info

    @patch('src.rollback.ConnectionManager')
    def test_rollback_without_verify(self, mock_conn_mgr_class, mock_device, test_backup_file, temp_dir, test_inventory_file):
        """Test rollback without verification."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_config_set.return_value = "Config applied"
        mock_conn_mgr.send_command.return_value = "! Current config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        result = rollback_mgr.rollback_device(mock_device, test_backup_file, verify=False)

        assert result['success'] is True

    def test_preview_backup(self, test_backup_file, temp_dir, test_inventory_file):
        """Test backup preview."""
        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        preview = rollback_mgr.preview_backup(test_backup_file)

        # preview_backup returns a formatted string
        assert isinstance(preview, str)
        assert 'test_device1' in preview or 'backup' in preview.lower()

    @patch('src.rollback.ConnectionManager')
    def test_rollback_multiple_devices(self, mock_conn_mgr_class, temp_dir, test_backup_file, test_inventory_file):
        """Test rollback to multiple devices."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_config_set.return_value = "Config applied"
        mock_conn_mgr.send_command.return_value = "! Current config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        # Get devices
        devices = rollback_mgr.inventory_loader.get_all_devices()

        # Create list of tuples (device, backup_path)
        devices_and_backups = [(device, test_backup_file) for device in devices]

        results = rollback_mgr.rollback_multiple_devices(devices_and_backups, parallel=False)

        assert isinstance(results, list)
        assert len(results) == 2
