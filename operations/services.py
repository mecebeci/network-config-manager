from concurrent.futures import ThreadPoolExecutor

from django.conf import settings

from network import rendering
from network.ssh import DeviceConnection, DeviceError

from .models import Backup


# ---------------------------------------------------------------------------
# Connection: shared by all operations
# ---------------------------------------------------------------------------

def connect(device):
    return DeviceConnection(device.ip, settings.DEVICE_USERNAME, settings.DEVICE_PASSWORD)


def fetch_config(device):
    with connect(device) as conn:
        return conn.get_config()

# --- end: connection ---


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

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

# --- end: backup ---


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

def render_configs(devices, template, variables):
    """{device: rendered text}, used by both the preview and deploy().

    Raises RenderError (unknown template, missing variable) before any device is touched.
    """
    return {device: rendering.render(template, device, variables) for device in devices}


def config_lines(text):
    """Rendered template -> lines to send; empty lines are dropped."""
    return [line for line in text.splitlines() if line.strip()]


def push_config(device, lines):
    """Send lines and commit on one connection; returns the config from before.

    On any error the candidate is discarded, so the device stays unchanged.
    """
    with connect(device) as conn:
        # Read first: after send_config the session is in candidate mode
        before = conn.get_config()
        try:
            conn.send_config(lines)
            conn.commit()
        except DeviceError:
            conn.discard()
            raise
    return before


def deploy(devices, template, variables, user):
    """Render the template for each device and push it in parallel.

    Returns one {'device', 'backup', 'error'} dict per device, in input order.
    The backup is the pre-deploy config, saved only if the deploy succeeded.
    """
    # Rendering is fast and touches no device, so do it up front; a RenderError
    # here stops the whole deploy before anything is sent
    configs = render_configs(devices, template, variables)

    with ThreadPoolExecutor() as pool:
        jobs = [(device, pool.submit(push_config, device, config_lines(configs[device])))
                for device in devices]

    results = []
    for device, future in jobs:
        try:
            before = future.result()
        except DeviceError as e:
            results.append({'device': device, 'backup': None, 'error': str(e)})
            continue
        backup = Backup.objects.create(
            device=device, content=before, reason=Backup.Reason.PRE_DEPLOY, created_by=user,
        )
        results.append({'device': device, 'backup': backup, 'error': None})
    return results

# --- end: deploy ---
