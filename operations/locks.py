import threading
from contextlib import contextmanager

from network.ssh import DeviceError

# device id -> Lock. Only valid inside one process (gunicorn --workers 1)
_locks = {}
_locks_guard = threading.Lock()


@contextmanager
def device_lock(device):
    """Allow one config change per device at a time; raises DeviceError if busy."""
    # Two requests must not create two different locks for the same device
    with _locks_guard:
        lock = _locks.setdefault(device.pk, threading.Lock())

    # Fail at once instead of waiting: the user sees it and can retry
    if not lock.acquire(blocking=False):
        raise DeviceError(f'{device.ip}: another operation is running on this device')
    try:
        yield
    finally:
        lock.release()
