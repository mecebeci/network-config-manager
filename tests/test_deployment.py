"""Tests for deployment module."""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.deployment import ConfigDeployment
from src.exceptions import ConnectionError, CommandExecutionError


@pytest.mark.unit
class TestConfigDeployment:
    """Test cases for ConfigDeployment class."""

    def test_init(self, test_inventory_file, temp_dir):
        """Test ConfigDeployment initialization."""
        deploy_mgr = ConfigDeployment(
            inventory_path=test_inventory_file,
            template_dir=temp_dir
        )
        # Check that template_engine is initialized (the actual attribute)
        assert deploy_mgr.template_engine is not None

    def test_init_invalid_inventory(self, temp_dir):
        """Test initialization with invalid inventory."""
        with pytest.raises(Exception):
            ConfigDeployment(
                inventory_path="/nonexistent/inventory.yaml",
                template_dir=temp_dir
            )

    @patch('src.deployment.ConnectionManager')
    def test_deploy_to_device_success(self, mock_conn_mgr_class, mock_device, temp_dir, test_template_file, test_inventory_file):
        """Test successful configuration deployment."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_config_set.return_value = "Config applied"
        mock_conn_mgr.send_command.return_value = "! Current config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        deploy_mgr = ConfigDeployment(
            inventory_path=test_inventory_file,
            template_dir=temp_dir
        )

        variables = {
            'hostname': 'test_device1',
            'role': 'spine',
            'location': 'lab',
            'timestamp': '2025-02-03 12:00:00',
            'ntp_server': '10.0.0.1'
        }
        result = deploy_mgr.deploy_to_device(mock_device, 'test_template.j2', variables)

        assert result['success'] is True
        assert result['device_name'] == 'test_device1'

    @patch('src.deployment.ConnectionManager')
    def test_deploy_to_device_connection_failure(self, mock_conn_mgr_class, mock_device, temp_dir, test_inventory_file):
        """Test deployment with connection failure."""
        # Mock connection failure
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.side_effect = ConnectionError("Connection failed", device_name="test_device1")
        mock_conn_mgr_class.return_value = mock_conn_mgr

        deploy_mgr = ConfigDeployment(
            inventory_path=test_inventory_file,
            template_dir=temp_dir
        )

        variables = {'hostname': 'test_device1', 'role': 'spine', 'location': 'lab', 'timestamp': '2025-02-03', 'ntp_server': '10.0.0.1'}
        result = deploy_mgr.deploy_to_device(mock_device, 'test_template.j2', variables)

        assert result['success'] is False
        assert 'error' in result

    @patch('src.deployment.ConnectionManager')
    def test_dry_run_deployment(self, mock_conn_mgr_class, mock_device, temp_dir, test_template_file, test_inventory_file):
        """Test dry-run deployment."""
        # Mock connection for backup
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_command.return_value = "! Current config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        deploy_mgr = ConfigDeployment(
            inventory_path=test_inventory_file,
            template_dir=temp_dir
        )

        variables = {
            'hostname': 'test_device1',
            'role': 'spine',
            'location': 'lab',
            'timestamp': '2025-02-03 12:00:00',
            'ntp_server': '10.0.0.1'
        }
        result = deploy_mgr.deploy_to_device(mock_device, 'test_template.j2', variables, dry_run=True)

        # In dry-run mode, should preview but not deploy
        assert result['success'] is True
        assert result.get('dry_run') is True

    @patch('src.deployment.ConnectionManager')
    def test_deploy_to_multiple_devices(self, mock_conn_mgr_class, temp_dir, test_template_file, test_inventory_file):
        """Test deploying to multiple devices."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_config_set.return_value = "Config applied"
        mock_conn_mgr.send_command.return_value = "! Current config"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        deploy_mgr = ConfigDeployment(
            inventory_path=test_inventory_file,
            template_dir=temp_dir
        )

        # Get devices from inventory
        devices = deploy_mgr.inventory_loader.get_all_devices()

        # Create variables list matching device order
        variables_list = [
            {
                'hostname': device['name'],
                'role': device.get('role', 'unknown'),
                'location': device.get('location', 'lab'),
                'timestamp': '2025-02-03 12:00:00',
                'ntp_server': '10.0.0.1'
            }
            for device in devices
        ]

        results = deploy_mgr.deploy_to_multiple_devices(
            devices=devices,
            template_name='test_template.j2',
            variables_list=variables_list,
            parallel=False
        )

        assert isinstance(results, list)
        assert len(results) == 2  # test_inventory has 2 devices

    @patch('src.deployment.ConnectionManager')
    def test_preview_deployment(self, mock_conn_mgr_class, mock_device, temp_dir, test_template_file, test_inventory_file):
        """Test deployment preview."""
        deploy_mgr = ConfigDeployment(
            inventory_path=test_inventory_file,
            template_dir=temp_dir
        )

        variables = {
            'hostname': 'test_device1',
            'role': 'spine',
            'location': 'lab',
            'timestamp': '2025-02-03 12:00:00',
            'ntp_server': '10.0.0.1'
        }

        preview = deploy_mgr.preview_deployment(mock_device, 'test_template.j2', variables)

        # preview_deployment returns a formatted string
        assert isinstance(preview, str)
        assert 'test_device1' in preview
        assert 'ntp' in preview.lower()
