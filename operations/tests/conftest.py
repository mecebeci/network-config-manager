from unittest.mock import patch

import pytest
from django.core.management import call_command

from devices.models import Device
from network.ssh import DeviceError


@pytest.fixture
def lab_devices(db):
    call_command('loaddata', 'lab', verbosity=0)
    return Device.objects.all()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(username='alice', password='pw')


def fake_fetch(device):
    """Stands in for SSH: leaf2 is unreachable, every other device answers."""
    if device.name == 'leaf2':
        raise DeviceError(f'{device.ip}: cannot connect')
    return f'set / system name host-name {device.name}'


@pytest.fixture
def ssh():
    with patch('operations.services.fetch_config', side_effect=fake_fetch) as fetch:
        yield fetch


def fake_push(device, lines):
    """Stands in for push_config: leaf2 is unreachable, others return their old config."""
    return fake_fetch(device)


@pytest.fixture
def push():
    with patch('operations.services.push_config', side_effect=fake_push) as push:
        yield push
