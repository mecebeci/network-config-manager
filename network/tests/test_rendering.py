from types import SimpleNamespace

import pytest
from jinja2 import DictLoader

from network import rendering
from network.rendering import RenderError, list_templates, render, user_variables

DEVICE = SimpleNamespace(name='spine1', ip='172.21.20.11', role='spine')


@pytest.fixture
def templates(monkeypatch):
    """Swap the template folder for in-memory templates."""
    monkeypatch.setattr(rendering.env, 'loader', DictLoader({
        'ntp.j2': 'set / system ntp server {{ ntp_server }}\n',
        'iface.j2': (
            '{% set subif = subif_id | default(0) %}'
            '{{ hostname }} {{ ip }} {{ role }} {{ name }}.{{ subif }}'
            '{% for s in servers %}{{ s }}{% endfor %}'
        ),
        'README.md': 'not a template',
    }))


def test_lists_only_j2_files(templates):
    assert list_templates() == ['iface.j2', 'ntp.j2']


def test_user_variables_skip_auto_and_local_names(templates):
    assert user_variables('iface.j2') == ['name', 'servers', 'subif_id']


def test_render_fills_device_fields(templates):
    output = render('iface.j2', DEVICE, {'name': 'e1', 'servers': ['a', 'b']})
    assert output == 'spine1 172.21.20.11 spine e1.0ab'


def test_empty_field_counts_as_not_given(templates):
    output = render('iface.j2', DEVICE, {'name': 'e1', 'servers': [], 'subif_id': ''})
    assert output.endswith('e1.0')


def test_user_cannot_override_device_fields(templates):
    output = render('iface.j2', DEVICE, {'name': 'e1', 'servers': [], 'hostname': 'evil'})
    assert output.startswith('spine1 ')


def test_missing_variable_raises(templates):
    with pytest.raises(RenderError, match="'ntp_server' is undefined"):
        render('ntp.j2', DEVICE, {'ntp_server': ''})


@pytest.mark.parametrize('name', ['README.md', '../config/settings.py', 'nope.j2'])
def test_unknown_template_is_rejected(templates, name):
    with pytest.raises(RenderError, match='unknown template'):
        render(name, DEVICE, {})
    with pytest.raises(RenderError, match='unknown template'):
        user_variables(name)


def test_interface_template_without_ip():
    output = render('example_interface.j2', DEVICE, {
        'interface_name': 'ethernet-1/3', 'description': '', 'ip_address': '',
        'netmask': '', 'subinterface_id': '',
    })
    assert 'subinterface 0 admin-state enable' in output
    assert 'ipv4' not in output


def test_real_templates_have_no_bang_comments():
    # SR Linux rejects '!' lines ('Parsing error'); '#' is its comment character
    for name in list_templates():
        source = rendering.env.loader.get_source(rendering.env, name)[0]
        assert not any(line.startswith('!') for line in source.splitlines()), name
