from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, UndefinedError, meta

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / 'device_templates'

# Filled from the device and the clock, so the form does not ask for them
AUTO_VARIABLES = {'hostname', 'ip', 'role', 'timestamp'}

env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    # A missing variable fails the render instead of silently printing ''
    undefined=StrictUndefined,
    # {% if %} / {% for %} lines leave no blank lines or indentation behind
    trim_blocks=True,
    lstrip_blocks=True,
)


class RenderError(Exception):
    """Unknown template or missing variable; the message is shown to the user."""


def list_templates():
    return env.list_templates(extensions=['j2'])


def _load(name):
    # Only names from the list, so a crafted name cannot open any other file
    if name not in list_templates():
        raise RenderError(f'unknown template: {name}')
    return env.get_template(name)


def user_variables(name):
    """Sorted names of the variables the user has to fill in."""
    template = _load(name)
    source = env.loader.get_source(env, template.name)[0]
    return sorted(meta.find_undeclared_variables(env.parse(source)) - AUTO_VARIABLES)


def render(name, device, variables):
    """Render a template for one device (any object with name, ip and role)."""
    template = _load(name)
    context = {
        # An empty form field counts as not given, so default() filters apply
        **{key: value for key, value in variables.items() if value != ''},
        # Auto values last: the user cannot override the device's own hostname
        'hostname': device.name,
        'ip': device.ip,
        'role': device.role,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    try:
        return template.render(context)
    except UndefinedError as e:
        raise RenderError(f'{name}: {e}') from e
