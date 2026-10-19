import logging
import re

from netmiko import ConnectHandler
from netmiko.exceptions import (
    ConfigInvalidException,
    NetmikoAuthenticationException,
    NetmikoBaseException,
    SSHException,
)

logger = logging.getLogger(__name__)

# SR Linux reports a rejected command as output text, not as an SSH error
ERROR_PATTERN = r'^\s*(Parsing error|Error\b).*$'


class DeviceError(Exception):
    """Any failure talking to a device; the message is shown to the user."""


class DeviceConnection:
    """SSH session to an SR Linux device, used as a context manager.

    After send_config the session stays in candidate mode, so get_config
    must be called before sending changes to read the running config.
    """

    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self._conn = None

    def __enter__(self):
        try:
            self._conn = ConnectHandler(
                device_type='nokia_srl',
                host=self.host,
                username=self.username,
                password=self.password,
                # Log in with the password only, never with local SSH keys or agent
                use_keys=False,
                allow_agent=False,
            )
        # Authentication is a subclass of SSHException, so it must come first
        except NetmikoAuthenticationException as e:
            raise DeviceError(f'{self.host}: authentication failed') from e
        except (SSHException, NetmikoBaseException) as e:
            raise DeviceError(f'{self.host}: cannot connect: {e}') from e
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._conn.disconnect()

    def get_config(self):
        """Running config as flat 'set / ...' lines."""
        try:
            output = self._conn.send_command('info flat')
        except NetmikoBaseException as e:
            raise DeviceError(f'{self.host}: reading config failed: {e}') from e
        # Without this check an error message would be saved as a backup
        self._raise_on_error(output)
        return output

    def send_config(self, lines):
        """Send lines into the candidate config; nothing is applied until commit()."""
        try:
            return self._conn.send_config_set(lines, error_pattern=ERROR_PATTERN)
        # Netmiko stops at the first line whose output matches ERROR_PATTERN
        except ConfigInvalidException as e:
            raise DeviceError(f'{self.host}: command rejected: {e}') from e
        except NetmikoBaseException as e:
            raise DeviceError(f'{self.host}: sending config failed: {e}') from e

    def commit(self):
        try:
            output = self._conn.commit()
        except NetmikoBaseException as e:
            raise DeviceError(f'{self.host}: commit failed: {e}') from e
        # Netmiko does not check commit output; a failed validation shows up here
        self._raise_on_error(output)
        return output

    def discard(self):
        """Drop uncommitted candidate changes. Best effort: called while handling another error."""
        try:
            self._conn.send_command('discard stay', expect_string=r'#')
        # Raising here would hide the original error, so only log it
        except NetmikoBaseException as e:
            logger.warning('%s: discard failed: %s', self.host, e)

    def _raise_on_error(self, output):
        match = re.search(ERROR_PATTERN, output, flags=re.MULTILINE)
        if match:
            # The reason can span several lines ('Error in /system/ntp:' + details),
            # so keep everything from the first error line up to the next prompt
            error = output[match.start():].split('\n--{')[0]
            raise DeviceError(f'{self.host}: ' + ' '.join(error.split()))
