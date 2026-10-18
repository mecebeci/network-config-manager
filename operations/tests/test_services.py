from unittest.mock import call, patch

import pytest

from network.rendering import RenderError
from network.ssh import DeviceError
from operations.models import Backup
from operations.services import deploy, fetch_config, push_config, take_backup, take_backups

# lab_devices, user, ssh and push fixtures come from conftest.py


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


@pytest.fixture
def conn():
    """The DeviceConnection that push_config opens."""
    with patch('operations.services.DeviceConnection') as connection:
        conn = connection.return_value.__enter__.return_value
        conn.get_config.return_value = 'old config'
        yield conn


def test_push_config_reads_old_config_before_sending(lab_devices, conn):
    assert push_config(lab_devices.get(name='spine1'), ['set / a']) == 'old config'
    assert conn.method_calls == [call.get_config(), call.send_config(['set / a']), call.commit()]


@pytest.mark.parametrize('failing_step', ['send_config', 'commit'])
def test_push_config_discards_on_error(lab_devices, conn, failing_step):
    getattr(conn, failing_step).side_effect = DeviceError('rejected')
    with pytest.raises(DeviceError, match='rejected'):
        push_config(lab_devices.get(name='spine1'), ['set / a'])
    conn.discard.assert_called_once()


def test_deploy_sends_rendered_lines_without_blank_lines(lab_devices, user, push):
    spine1 = lab_devices.get(name='spine1')
    deploy([spine1], 'example_ntp.j2', {'ntp_server': '10.0.0.1'}, user)

    lines = push.call_args.args[1]
    assert lines[0] == '# NTP Configuration for spine1'
    assert 'set / system ntp server 10.0.0.1 prefer true' in lines
    assert '' not in lines


def test_deploy_saves_pre_deploy_backup_only_on_success(lab_devices, user, push):
    results = deploy(lab_devices, 'example_ntp.j2', {'ntp_server': '10.0.0.1'}, user)

    assert [r['device'].name for r in results] == ['leaf1', 'leaf2', 'spine1', 'spine2']
    assert results[1]['backup'] is None
    assert results[1]['error'] == '172.21.20.14: cannot connect'

    for r in [results[0], results[2], results[3]]:
        assert r['error'] is None
        assert r['backup'].reason == 'pre-deploy'
        assert r['backup'].content == f'set / system name host-name {r["device"].name}'
    assert Backup.objects.count() == 3


def test_deploy_render_error_touches_no_device(lab_devices, user, push):
    with pytest.raises(RenderError, match="'ntp_server' is undefined"):
        deploy(lab_devices, 'example_ntp.j2', {'ntp_server': ''}, user)
    push.assert_not_called()
    assert not Backup.objects.exists()
