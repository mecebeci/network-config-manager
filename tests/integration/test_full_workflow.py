"""Integration tests for full workflows."""

import pytest
import os
from unittest.mock import patch, MagicMock
from src.inventory_loader import InventoryLoader
from src.template_engine import TemplateEngine
from src.backup import ConfigBackup
from src.deployment import ConfigDeployment
from src.rollback import ConfigRollback


@pytest.mark.integration
class TestFullWorkflow:
    """Test complete workflows integrating multiple components."""

    def test_inventory_to_template_workflow(self, test_inventory_file, test_template_file, temp_dir):
        """Test loading inventory and rendering template."""
        # Load inventory
        loader = InventoryLoader(inventory_path=test_inventory_file)
        device = loader.get_device_by_name('test_device1')
        assert device is not None

        # Render template
        engine = TemplateEngine(template_dir=temp_dir)
        variables = {
            'hostname': device['name'],
            'role': device.get('role', 'unknown'),
            'location': device.get('location', 'unknown'),
            'timestamp': '2025-02-03 12:00:00',
            'ntp_server': '10.0.0.1'
        }
        result = engine.render_template('test_template.j2', variables)

        assert device['name'] in result
        assert '10.0.0.1' in result

    def test_inventory_loader_integration(self, test_inventory_file):
        """Test inventory loader with multiple operations."""
        loader = InventoryLoader(inventory_path=test_inventory_file)

        # Test getting all devices
        all_devices = loader.get_all_devices()
        assert len(all_devices) == 2

        # Test filtering by role
        spines = loader.get_devices_by_role('spine')
        leafs = loader.get_devices_by_role('leaf')
        assert len(spines) == 1
        assert len(leafs) == 1

        # Test settings
        settings = loader.get_settings()
        assert settings['default_username'] == 'admin'

    def test_template_engine_integration(self, temp_dir, test_template_file):
        """Test template engine with multiple templates and variables."""
        engine = TemplateEngine(template_dir=temp_dir)

        # Test listing templates
        templates = engine.list_templates()
        assert len(templates) > 0

        # Test rendering multiple times with different variables
        variables_list = [
            {'hostname': 'spine1', 'role': 'spine', 'location': 'lab', 'timestamp': '2025-02-03 12:00:00', 'ntp_server': '10.0.0.1'},
            {'hostname': 'leaf1', 'role': 'leaf', 'location': 'lab', 'timestamp': '2025-02-03 12:00:00', 'ntp_server': '10.0.0.1'},
        ]

        for variables in variables_list:
            result = engine.render_template('test_template.j2', variables)
            assert variables['hostname'] in result

    @patch('src.backup.ConnectionManager')
    def test_backup_workflow(self, mock_conn_mgr_class, test_inventory_file, temp_dir):
        """Test complete backup workflow."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_command.return_value = "! Test configuration\nhostname test_device"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        # Initialize backup manager
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        # Get devices
        devices = backup_mgr.inventory_loader.get_all_devices()
        assert len(devices) > 0

        # Backup first device
        device = backup_mgr.inventory_loader.get_device_by_name('test_device1')
        result = backup_mgr.backup_device(device)

        assert result['success'] is True
        assert os.path.exists(result['filepath'])

        # List backups
        backups = backup_mgr.list_device_backups('test_device1')
        assert len(backups) > 0

    @patch('src.deployment.ConnectionManager')
    def test_deployment_workflow(self, mock_conn_mgr_class, test_inventory_file, test_template_file, temp_dir):
        """Test complete deployment workflow."""
        # Mock connection
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.__enter__.return_value = mock_conn_mgr
        mock_conn_mgr.__exit__.return_value = None
        mock_conn_mgr.send_config.return_value = "Configuration applied"
        mock_conn_mgr_class.return_value = mock_conn_mgr

        # Initialize deployment manager
        deploy_mgr = ConfigDeployment(
            inventory_path=test_inventory_file,
            template_dir=temp_dir
        )

        # Get device
        device = deploy_mgr.inventory_loader.get_device_by_name('test_device1')
        assert device is not None

        # Prepare configuration
        variables = {
            'hostname': device['name'],
            'role': device.get('role', 'unknown'),
            'location': device.get('location', 'unknown'),
            'timestamp': '2025-02-03 12:00:00',
            'ntp_server': '10.0.0.1'
        }

        # Deploy from template
        result = deploy_mgr.deploy_to_device(device, 'test_template.j2', variables)
        assert result['success'] is True

    @patch('src.backup.ConnectionManager')
    @patch('src.rollback.ConnectionManager')
    def test_backup_and_rollback_workflow(self, mock_rollback_conn, mock_backup_conn, test_inventory_file, temp_dir):
        """Test complete backup and rollback workflow."""
        # Mock backup connection
        mock_backup_mgr = MagicMock()
        mock_backup_mgr.__enter__.return_value = mock_backup_mgr
        mock_backup_mgr.__exit__.return_value = None
        mock_backup_mgr.send_command.return_value = "! Original configuration"
        mock_backup_conn.return_value = mock_backup_mgr

        # Mock rollback connection
        mock_rollback_mgr = MagicMock()
        mock_rollback_mgr.__enter__.return_value = mock_rollback_mgr
        mock_rollback_mgr.__exit__.return_value = None
        mock_rollback_mgr.send_config.return_value = "Configuration restored"
        mock_rollback_conn.return_value = mock_rollback_mgr

        # Step 1: Backup device
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        device = backup_mgr.inventory_loader.get_device_by_name('test_device1')
        backup_result = backup_mgr.backup_device(device)

        assert backup_result['success'] is True
        backup_file = backup_result['filepath']
        assert os.path.exists(backup_file)

        # Step 2: Rollback to backup
        rollback_mgr = ConfigRollback(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )

        rollback_result = rollback_mgr.rollback_device(device, backup_file)
        assert rollback_result['success'] is True

    def test_multi_device_operations(self, test_inventory_file, temp_dir):
        """Test operations across multiple devices."""
        # Load inventory
        loader = InventoryLoader(inventory_path=test_inventory_file)

        # Get devices by role
        spine_devices = loader.get_devices_by_role('spine')
        leaf_devices = loader.get_devices_by_role('leaf')

        assert len(spine_devices) > 0
        assert len(leaf_devices) > 0

        # Verify device attributes
        for device in spine_devices:
            assert device['role'] == 'spine'
            assert 'name' in device
            assert 'ip' in device

        for device in leaf_devices:
            assert device['role'] == 'leaf'
            assert 'name' in device
            assert 'ip' in device

    def test_template_with_inventory_integration(self, test_inventory_file, test_template_file, temp_dir):
        """Test rendering templates for all devices from inventory."""
        # Load inventory
        loader = InventoryLoader(inventory_path=test_inventory_file)
        devices = loader.get_all_devices()

        # Initialize template engine
        engine = TemplateEngine(template_dir=temp_dir)

        # Render template for each device
        for device in devices:
            variables = {
                'hostname': device['name'],
                'role': device.get('role', 'unknown'),
                'location': device.get('location', 'unknown'),
                'timestamp': '2025-02-03 12:00:00',
                'ntp_server': '10.0.0.1'
            }

            result = engine.render_template('test_template.j2', variables)
            assert device['name'] in result
            assert 'ntp' in result.lower()


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEndWorkflow:
    """Test end-to-end workflows that may take longer."""

    @patch('src.backup.ConnectionManager')
    @patch('src.deployment.ConnectionManager')
    def test_full_config_lifecycle(self, mock_deploy_conn, mock_backup_conn, test_inventory_file, test_template_file, temp_dir):
        """Test complete configuration lifecycle: backup -> deploy -> verify."""
        # Setup mocks
        mock_backup_mgr = MagicMock()
        mock_backup_mgr.__enter__.return_value = mock_backup_mgr
        mock_backup_mgr.__exit__.return_value = None
        mock_backup_mgr.send_command.return_value = "! Configuration backup"
        mock_backup_conn.return_value = mock_backup_mgr

        mock_deploy_mgr = MagicMock()
        mock_deploy_mgr.__enter__.return_value = mock_deploy_mgr
        mock_deploy_mgr.__exit__.return_value = None
        mock_deploy_mgr.send_config.return_value = "Configuration applied"
        mock_deploy_conn.return_value = mock_deploy_mgr

        # Load inventory
        loader = InventoryLoader(inventory_path=test_inventory_file)
        device = loader.get_device_by_name('test_device1')

        # Step 1: Backup current configuration
        backup_mgr = ConfigBackup(
            inventory_path=test_inventory_file,
            backup_dir=temp_dir
        )
        backup_result = backup_mgr.backup_device(device)
        assert backup_result['success'] is True

        # Step 2: Deploy new configuration
        deploy_mgr = ConfigDeployment(
            inventory_path=test_inventory_file,
            template_dir=temp_dir
        )
        variables = {
            'hostname': device['name'],
            'role': device.get('role', 'unknown'),
            'location': device.get('location', 'unknown'),
            'timestamp': '2025-02-03 12:00:00',
            'ntp_server': '10.0.0.1'
        }
        deploy_result = deploy_mgr.deploy_to_device(device, 'test_template.j2', variables)
        assert deploy_result['success'] is True

        # Step 3: Verify backup exists
        latest_backup = backup_mgr.get_latest_backup(device['name'])
        assert latest_backup is not None
