from unittest.mock import call, patch

import pytest

from network.rendering import RenderError
from network.ssh import DeviceError
from operations.models import Backup
from operations.services import (
    deploy,
    fetch_config,
    preview_rollback,
    push_config,
    push_rollback,
    rollback,
    rollback_commands,
    take_backup,
    take_backups,
)

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


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

# Running config after an NTP deploy, and the backup from before it
RUNNING = (
    'set / system name host-name spine1\n'
    'set / system ntp admin-state enable\n'
    'set / system ntp server 10.0.0.1\n'
)
TARGET = 'set / system name host-name spine1\nset / system ntp admin-state disable\n'
NTP_DELETES = ['delete / system ntp admin-state', 'delete / system ntp server']
# host-name is already on the device, so only the changed line is set
SEND = NTP_DELETES + ['set / system ntp admin-state disable']


@pytest.fixture
def ntp_backup(lab_devices):
    return Backup.objects.create(
        device=lab_devices.get(name='spine1'), content=TARGET, reason=Backup.Reason.MANUAL,
    )


def test_rollback_commands_sends_deletes_and_only_needed_sets():
    assert rollback_commands(RUNNING, TARGET) == {
        'deletes': NTP_DELETES,
        'sets': ['set / system ntp admin-state disable'],
        'send': SEND,
        'withheld': [],
        'skipped': [],
    }


def test_preview_rollback_reads_the_backups_device(ntp_backup):
    with patch('operations.services.fetch_config', return_value=RUNNING) as fetch:
        assert preview_rollback(ntp_backup)['send'] == SEND
    fetch.assert_called_once_with(ntp_backup.device)


def test_push_rollback_sends_previewed_commands_in_one_commit(ntp_backup, conn):
    conn.get_config.return_value = RUNNING
    assert push_rollback(ntp_backup, SEND) == RUNNING
    assert conn.method_calls == [call.get_config(), call.send_config(SEND), call.commit()]


def test_push_rollback_refuses_if_device_changed_since_preview(ntp_backup, conn):
    conn.get_config.return_value = RUNNING
    # The preview was made before 'ntp server' was added
    with pytest.raises(DeviceError, match='config changed since the preview'):
        push_rollback(ntp_backup, SEND[1:])
    conn.send_config.assert_not_called()
    conn.commit.assert_not_called()


def test_push_rollback_with_nothing_to_send_does_not_commit(ntp_backup, conn):
    conn.get_config.return_value = TARGET
    assert push_rollback(ntp_backup, []) == TARGET
    conn.send_config.assert_not_called()
    conn.commit.assert_not_called()


@pytest.mark.parametrize('failing_step', ['send_config', 'commit'])
def test_push_rollback_discards_on_error(ntp_backup, conn, failing_step):
    conn.get_config.return_value = RUNNING
    getattr(conn, failing_step).side_effect = DeviceError('rejected')
    with pytest.raises(DeviceError, match='rejected'):
        push_rollback(ntp_backup, SEND)
    conn.discard.assert_called_once()


def test_rollback_saves_pre_rollback_backup(ntp_backup, user):
    with patch('operations.services.push_rollback', return_value=RUNNING):
        before = rollback(ntp_backup, SEND, user)
    before.refresh_from_db()
    assert before.device == ntp_backup.device
    assert before.content == RUNNING
    assert before.reason == 'pre-rollback'
    assert before.created_by == user


def test_rollback_failure_saves_nothing(ntp_backup, user):
    with patch('operations.services.push_rollback', side_effect=DeviceError('rejected')):
        with pytest.raises(DeviceError):
            rollback(ntp_backup, SEND, user)
    assert list(Backup.objects.all()) == [ntp_backup]
