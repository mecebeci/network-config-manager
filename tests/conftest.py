"""Pytest configuration and shared fixtures."""

import pytest
import os
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def test_inventory_file(temp_dir):
    """Create test inventory YAML file."""
    inventory_content = """
settings:
  default_username: "admin"
  default_password: "password"
  default_device_type: "nokia_sros"
  connection_timeout: 10

devices:
  - name: test_device1
    ip: 192.168.1.1
    role: spine
    device_type: nokia_sros
    location: lab

  - name: test_device2
    ip: 192.168.1.2
    role: leaf
    device_type: nokia_sros
    location: lab
"""
    inventory_path = os.path.join(temp_dir, "test_inventory.yaml")
    with open(inventory_path, 'w') as f:
        f.write(inventory_content)
    return inventory_path


@pytest.fixture
def test_template_file(temp_dir):
    """Create test Jinja2 template file."""
    template_content = """
! Configuration for {{ hostname }}
! Generated: {{ timestamp }}

/system ntp
    server {{ ntp_server }}
"""
    template_path = os.path.join(temp_dir, "test_template.j2")
    with open(template_path, 'w') as f:
        f.write(template_content)
    return template_path


@pytest.fixture
def test_backup_file(temp_dir):
    """Create test backup configuration file."""
    backup_content = """
! Backup configuration
/interface ethernet-1/1
    admin-state enable
"""
    backup_path = os.path.join(temp_dir, "test_device1_20250203_120000.cfg")
    with open(backup_path, 'w') as f:
        f.write(backup_content)
    return backup_path


@pytest.fixture
def mock_device():
    """Return mock device dictionary."""
    return {
        'name': 'test_device1',
        'ip': '192.168.1.1',
        'username': 'admin',
        'password': 'password',
        'device_type': 'nokia_sros',
        'role': 'spine',
        'location': 'lab'
    }
