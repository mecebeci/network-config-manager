from unittest.mock import patch

import pytest
from netmiko.exceptions import (
    ConfigInvalidException,
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
    ReadTimeout,
)

from network.ssh import ERROR_PATTERN, DeviceConnection, DeviceError


@pytest.fixture
def netmiko():
    """Replace ConnectHandler; the returned mock stands in for the Netmiko session."""
    with patch('network.ssh.ConnectHandler') as handler:
        yield handler.return_value


def connect():
    return DeviceConnection('172.21.20.11', 'admin', 'secret')


def test_connects_as_srl_with_password_only():
    with patch('network.ssh.ConnectHandler') as handler:
        with connect():
            pass
    handler.assert_called_once_with(
        device_type='nokia_srl',
        host='172.21.20.11',
        username='admin',
        password='secret',
        use_keys=False,
        allow_agent=False,
    )


def test_disconnects_even_when_block_raises(netmiko):
    with pytest.raises(RuntimeError):
        with connect():
            raise RuntimeError('boom')
    netmiko.disconnect.assert_called_once()


def test_authentication_failure_raises_device_error():
    with patch('network.ssh.ConnectHandler', side_effect=NetmikoAuthenticationException('bad')):
        with pytest.raises(DeviceError, match='authentication failed'):
            with connect():
                pass


def test_unreachable_device_raises_device_error():
    with patch('network.ssh.ConnectHandler', side_effect=NetmikoTimeoutException('timed out')):
        with pytest.raises(DeviceError, match='cannot connect'):
            with connect():
                pass


def test_get_config_returns_info_flat_output(netmiko):
    netmiko.send_command.return_value = 'set / system name host-name spine1\n'
    with connect() as conn:
        assert conn.get_config() == 'set / system name host-name spine1\n'
    netmiko.send_command.assert_called_once_with('info flat')


def test_get_config_rejects_error_output(netmiko):
    netmiko.send_command.return_value = "Parsing error: Unknown token 'flat'"
    with connect() as conn:
        with pytest.raises(DeviceError, match='Parsing error'):
            conn.get_config()


def test_get_config_read_timeout_raises_device_error(netmiko):
    netmiko.send_command.side_effect = ReadTimeout('no prompt')
    with connect() as conn:
        with pytest.raises(DeviceError, match='reading config failed'):
            conn.get_config()


def test_send_config_passes_error_pattern(netmiko):
    lines = ['set / system ntp admin-state enable']
    with connect() as conn:
        conn.send_config(lines)
    netmiko.send_config_set.assert_called_once_with(lines, error_pattern=ERROR_PATTERN)


def test_send_config_rejected_command_raises_device_error(netmiko):
    netmiko.send_config_set.side_effect = ConfigInvalidException('Invalid input detected')
    with connect() as conn:
        with pytest.raises(DeviceError, match='command rejected'):
            conn.send_config(['set / system ntp server abc'])


def test_commit_error_includes_reason(netmiko):
    # Real SR Linux output for an NTP server without a network-instance
    netmiko.commit.return_value = (
        'commit stay\n'
        'Error in /system/ntp:\n'
        '    NTP mandatory network-instance configuration missing.\n'
        'Error: Commit failed\n'
        '\n'
        '--{ * candidate private private-admin }--[  ]--\n'
        'A:admin@spine1# '
    )
    with connect() as conn:
        with pytest.raises(DeviceError) as error:
            conn.commit()
    assert str(error.value) == (
        '172.21.20.11: Error in /system/ntp: '
        'NTP mandatory network-instance configuration missing. Error: Commit failed'
    )


def test_successful_commit_returns_output(netmiko):
    output = 'commit stay\n\n--{ + candidate private private-admin }--[  ]--\nA:admin@spine1# '
    netmiko.commit.return_value = output
    with connect() as conn:
        assert conn.commit() == output


def test_discard_does_not_raise(netmiko):
    netmiko.send_command.side_effect = ReadTimeout('no prompt')
    with connect() as conn:
        conn.discard()
    netmiko.send_command.assert_called_once_with('discard stay', expect_string=r'#')
