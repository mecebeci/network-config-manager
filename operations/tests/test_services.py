from unittest.mock import patch

import pytest

from network.ssh import DeviceError
from operations.models import Backup
from operations.services import fetch_config, take_backup, take_backups

# lab_devices, user and ssh fixtures come from conftest.py


def test_fetch_config_uses_device_ip_and_env_credentials(lab_devices, settings):
    settings.DEVICE_USERNAME = 'admin'
    settings.DEVICE_PASSWORD = 'secret'
    spine1 = lab_devices.get(name='spine1')
    with patch('operations.services.DeviceConnection') as connection:
        conn = connection.return_value.__enter__.return_value
        conn.get_config.return_value = 'set / system name host-name spine1'
        assert fetch_config(spine1) == 'set / system name host-name spine1'
    connection.assert_called_once_with('172.21.20.11', 'admin', 'secret')


def test_take_backup_saves_config(lab_devices, user, ssh):
    spine1 = lab_devices.get(name='spine1')
    backup = take_backup(spine1, Backup.Reason.MANUAL, user)
    backup.refresh_from_db()
    assert backup.device == spine1
    assert backup.content == 'set / system name host-name spine1'
    assert backup.reason == 'manual'
    assert backup.created_by == user


def test_take_backup_failure_raises_and_saves_nothing(lab_devices, user, ssh):
    leaf2 = lab_devices.get(name='leaf2')
    with pytest.raises(DeviceError, match='cannot connect'):
        take_backup(leaf2, Backup.Reason.MANUAL, user)
    assert not Backup.objects.exists()


def test_take_backups_continues_after_one_device_fails(lab_devices, user, ssh):
    results = take_backups(lab_devices, Backup.Reason.MANUAL, user)

    # One result per device, in the order the devices were given
    assert [r['device'].name for r in results] == ['leaf1', 'leaf2', 'spine1', 'spine2']

    failed = results[1]
    assert failed['backup'] is None
    assert failed['error'] == '172.21.20.14: cannot connect'

    for r in [results[0], results[2], results[3]]:
        assert r['error'] is None
        assert r['backup'].content == f'set / system name host-name {r["device"].name}'

    assert Backup.objects.count() == 3
    assert not Backup.objects.filter(device__name='leaf2').exists()
