import pytest
from django.core.management import call_command
from pytest_django.asserts import assertContains


@pytest.fixture
def lab_devices(db):
    call_command('loaddata', 'lab', verbosity=0)


@pytest.fixture
def user_client(client, django_user_model):
    user = django_user_model.objects.create_user(username='alice', password='pw')
    client.force_login(user)
    return client


def device_names(response):
    return [device.name for device in response.context['devices']]


def test_list_shows_all_devices(user_client, lab_devices):
    response = user_client.get('/')
    assert device_names(response) == ['leaf1', 'leaf2', 'spine1', 'spine2']
    assertContains(response, '172.21.20.11')


def test_role_filter_shows_only_that_role(user_client, lab_devices):
    response = user_client.get('/?role=spine')
    assert device_names(response) == ['spine1', 'spine2']
    assert response.context['current_role'] == 'spine'


def test_unknown_role_is_ignored(user_client, lab_devices):
    response = user_client.get('/?role=core')
    assert device_names(response) == ['leaf1', 'leaf2', 'spine1', 'spine2']
    assert response.context['current_role'] is None
