from concurrent.futures import ThreadPoolExecutor

from django.conf import settings

from network.ssh import DeviceConnection, DeviceError

from .models import Backup


def connect(device):
    return DeviceConnection(device.ip, settings.DEVICE_USERNAME, settings.DEVICE_PASSWORD)


def fetch_config(device):
    with connect(device) as conn:
        return conn.get_config()


def take_backup(device, reason, user):
    """Save the device's running config. Raises DeviceError on failure."""
    content = fetch_config(device)
    return Backup.objects.create(device=device, content=content, reason=reason, created_by=user)


def take_backups(devices, reason, user):
    """Back up several devices in parallel; one failure does not stop the others.

    Returns one {'device', 'backup', 'error'} dict per device, in input order.
    """
    # Only SSH runs in threads; the database is written below in this thread.
    # Each device is kept together with its future: (device, future) pairs
    with ThreadPoolExecutor() as pool:
        jobs = [(device, pool.submit(fetch_config, device)) for device in devices]

    results = []
    for device, future in jobs:
        # result() re-raises the exception from the thread, if any
        try:
            content = future.result()
        except DeviceError as e:
            results.append({'device': device, 'backup': None, 'error': str(e)})
            continue
        backup = Backup.objects.create(
            device=device, content=content, reason=reason, created_by=user,
        )
        results.append({'device': device, 'backup': backup, 'error': None})
    return results
