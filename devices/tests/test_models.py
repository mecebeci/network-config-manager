import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError

from devices.models import Device

pytestmark = pytest.mark.django_db


def make_device(**kwargs):
    fields = {'name': 'spine1', 'ip': '172.21.20.11', 'role': Device.Role.SPINE}
    fields.update(kwargs)
    return Device(**fields)


def test_name_must_be_unique():
    make_device().save()
    with pytest.raises(IntegrityError):
        make_device(ip='172.21.20.99').save()


def test_ip_must_be_unique():
    make_device().save()
    with pytest.raises(IntegrityError):
        make_device(name='spine9').save()


def test_invalid_ip_is_rejected():
    with pytest.raises(ValidationError):
        make_device(ip='172.21.20.999').full_clean()


def test_unknown_role_is_rejected():
    with pytest.raises(ValidationError):
        make_device(role='core').full_clean()


def test_lab_fixture_loads_four_devices():
    call_command('loaddata', 'lab', verbosity=0)
    assert list(Device.objects.values_list('name', flat=True)) == ['leaf1', 'leaf2', 'spine1', 'spine2']
