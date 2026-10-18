from types import SimpleNamespace
from unittest.mock import patch

import pytest

from network.ssh import DeviceError
from operations.locks import device_lock
from operations.services import push_config

spine1 = SimpleNamespace(pk=1, ip='172.21.20.11')
leaf1 = SimpleNamespace(pk=3, ip='172.21.20.13')


def test_second_operation_on_same_device_is_refused():
    with device_lock(spine1):
        with pytest.raises(DeviceError, match='another operation is running'):
            with device_lock(spine1):
                pass


def test_different_devices_do_not_block_each_other():
    with device_lock(spine1):
        with device_lock(leaf1):
            pass


def test_lock_is_released_after_an_error():
    with pytest.raises(DeviceError):
        with device_lock(spine1):
            raise DeviceError('commit failed')
    # Would raise 'another operation is running' if the lock were still held
    with device_lock(spine1):
        pass


def test_push_config_on_busy_device_does_not_connect():
    with patch('operations.services.connect') as connect:
        with device_lock(spine1):
            with pytest.raises(DeviceError, match='another operation is running'):
                push_config(spine1, ['set / system ntp admin-state enable'])
    connect.assert_not_called()
