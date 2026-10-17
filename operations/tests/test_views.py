import pytest
from pytest_django.asserts import assertContains, assertRedirects

from operations.models import Backup

# lab_devices, user and ssh fixtures come from conftest.py


@pytest.fixture
def user_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def backup(lab_devices, user):
    spine1 = lab_devices.get(name='spine1')
    return Backup.objects.create(
        device=spine1, content='set / system name host-name spine1',
        reason=Backup.Reason.MANUAL, created_by=user,
    )


@pytest.mark.parametrize('url', ['/backup/', '/devices/1/backups/', '/backups/1/'])
def test_pages_require_login(client, db, url):
    response = client.get(url)
    assertRedirects(response, f'/login/?next={url}', fetch_redirect_response=False)


def test_select_role_preticks_those_devices(user_client, lab_devices):
    response = user_client.get('/backup/?select=spine')
    ticked = response.context['form'].initial['devices']
    assert sorted(d.name for d in ticked) == ['spine1', 'spine2']


def test_run_rejects_get(user_client, db):
    assert user_client.get('/backup/run/').status_code == 405


def test_run_without_selection_shows_error(user_client, lab_devices, ssh):
    response = user_client.post('/backup/run/', {})
    assertContains(response, 'Select at least one device.')
    ssh.assert_not_called()


def test_run_backs_up_only_selected_devices(user_client, lab_devices, ssh):
    spine1 = lab_devices.get(name='spine1')
    leaf2 = lab_devices.get(name='leaf2')
    response = user_client.post('/backup/run/', {'devices': [spine1.pk, leaf2.pk]})

    assertContains(response, 'Saved')
    assertContains(response, '172.21.20.14: cannot connect')
    backup = Backup.objects.get()
    assert backup.device == spine1
    assert backup.reason == 'manual'
    assert backup.created_by.username == 'alice'


def test_device_backups_lists_only_that_device(user_client, backup, lab_devices):
    Backup.objects.create(device=lab_devices.get(name='leaf1'), content='x', reason='manual')
    response = user_client.get(f'/devices/{backup.device.pk}/backups/')
    assert list(response.context['backups']) == [backup]


def test_backup_detail_shows_content(user_client, backup):
    response = user_client.get(f'/backups/{backup.pk}/')
    assertContains(response, 'set / system name host-name spine1')


def test_download_returns_config_as_attachment(user_client, backup):
    response = user_client.get(f'/backups/{backup.pk}/download/')
    assert response.content == b'set / system name host-name spine1'
    assert response['Content-Disposition'].startswith('attachment; filename="spine1_')


def test_unknown_backup_is_404(user_client, db):
    assert user_client.get('/backups/999/').status_code == 404
