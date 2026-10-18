from unittest.mock import patch

import pytest
from django.core import signing
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from network.ssh import DeviceError
from operations.models import Backup
from operations.views import DEPLOY_SALT, ROLLBACK_SALT

# lab_devices, user, ssh and push fixtures come from conftest.py


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


@pytest.mark.parametrize('url', [
    '/backup/', '/devices/1/backups/', '/backups/1/', '/backups/compare/', '/rollback/1/',
])
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


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

NTP = {'template': 'example_ntp.j2', 'var_ntp_server': '10.0.0.1'}


@pytest.mark.parametrize('url', ['/deploy/', '/deploy/form/'])
def test_deploy_pages_require_login(client, db, url):
    response = client.get(url)
    assertRedirects(response, f'/login/?next={url}', fetch_redirect_response=False)


def test_deploy_form_shows_template_variables(user_client, db):
    response = user_client.get('/deploy/form/?template=example_ntp.j2')
    assertContains(response, 'name="var_ntp_server"')


def preview(user_client, lab_devices, **data):
    spine1 = lab_devices.get(name='spine1')
    return user_client.post('/deploy/preview/', {'devices': [spine1.pk], **NTP, **data})


def test_preview_shows_config_and_touches_no_device(user_client, lab_devices, push):
    response = preview(user_client, lab_devices)
    assertContains(response, 'set / system ntp server 10.0.0.1 prefer true')
    assertContains(response, 'name="plan"')
    push.assert_not_called()


def test_preview_missing_variable_shows_error_without_plan(user_client, lab_devices, push):
    response = preview(user_client, lab_devices, var_ntp_server='')
    assertContains(response, 'is undefined')
    assertNotContains(response, 'name="plan"')


def test_apply_runs_the_previewed_plan(user_client, lab_devices, push):
    plan = preview(user_client, lab_devices).context['plan']
    response = user_client.post('/deploy/apply/', {'plan': plan})

    assertContains(response, 'Committed')
    device, lines = push.call_args.args
    assert device.name == 'spine1'
    assert 'set / system ntp server 10.0.0.1 prefer true' in lines
    assert Backup.objects.get().reason == 'pre-deploy'


def test_apply_rejects_changed_plan(user_client, lab_devices, push):
    plan = preview(user_client, lab_devices).context['plan']
    # Keep the signature, swap the content for another NTP server
    signature = plan.rsplit(':', 1)[1]
    evil = signing.dumps({**signing.loads(plan, salt=DEPLOY_SALT),
                          'variables': {'ntp_server': '6.6.6.6'}}, salt=DEPLOY_SALT)
    forged = evil.rsplit(':', 1)[0] + ':' + signature

    response = user_client.post('/deploy/apply/', {'plan': forged})
    assert response.status_code == 400
    push.assert_not_called()


@pytest.mark.parametrize('plan', ['', 'not-a-plan'])
def test_apply_rejects_missing_or_garbage_plan(user_client, db, push, plan):
    assert user_client.post('/deploy/apply/', {'plan': plan}).status_code == 400
    push.assert_not_called()


def test_apply_rejects_plan_signed_for_something_else(user_client, lab_devices, push):
    plan = signing.dumps({'devices': [1], 'template': 'example_ntp.j2', 'variables': {}},
                         salt='other.purpose')
    assert user_client.post('/deploy/apply/', {'plan': plan}).status_code == 400
    push.assert_not_called()


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

def test_compare_shows_diff(user_client, backup):
    newer = Backup.objects.create(
        device=backup.device, content='set / system name host-name spine1-new', reason='manual',
    )
    response = user_client.get(f'/backups/compare/?a={backup.pk}&b={newer.pk}')
    assertContains(response, '<del>-set / system name host-name spine1</del>', html=False)
    assertContains(response, '<ins>+set / system name host-name spine1-new</ins>', html=False)


def test_compare_same_backup_says_identical(user_client, backup):
    response = user_client.get(f'/backups/compare/?a={backup.pk}&b={backup.pk}')
    assertContains(response, 'identical')


@pytest.mark.parametrize('query', ['a=abc&b=1', 'a=999&b=1', 'a=1'])
def test_compare_with_bad_ids_is_400(user_client, backup, query):
    assert user_client.get(f'/backups/compare/?{query}').status_code == 400


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

# The device runs 'backup' plus one extra line, so rolling back only deletes it
RUNNING = 'set / system name host-name spine1\nset / system ntp admin-state enable\n'
SEND = ['delete / system ntp']


@pytest.fixture
def running():
    with patch('operations.services.fetch_config', return_value=RUNNING) as fetch:
        yield fetch


@pytest.fixture
def push_rollback():
    with patch('operations.services.push_rollback', return_value=RUNNING) as push:
        yield push


def test_rollback_preview_shows_commands_and_plan(user_client, backup, running):
    response = user_client.get(f'/rollback/{backup.pk}/')
    assertContains(response, 'delete / system ntp')
    assertContains(response, 'Nothing to set')
    plan = signing.loads(response.context['plan'], salt=ROLLBACK_SALT)
    assert plan == {'backup': backup.pk, 'send': SEND}


def test_rollback_preview_of_matching_device_offers_no_apply(user_client, backup):
    with patch('operations.services.fetch_config', return_value=backup.content):
        response = user_client.get(f'/rollback/{backup.pk}/')
    assertContains(response, 'already matches this backup')
    assertNotContains(response, 'name="plan"')


def test_rollback_preview_unreachable_device_shows_error_without_plan(user_client, backup):
    with patch('operations.services.fetch_config', side_effect=DeviceError('cannot connect')):
        response = user_client.get(f'/rollback/{backup.pk}/')
    assertContains(response, 'cannot connect')
    assertNotContains(response, 'name="plan"')


def test_rollback_apply_rejects_get(user_client, db):
    assert user_client.get('/rollback/apply/').status_code == 405


def test_rollback_apply_runs_the_previewed_plan(user_client, backup, running, push_rollback):
    plan = user_client.get(f'/rollback/{backup.pk}/').context['plan']
    response = user_client.post('/rollback/apply/', {'plan': plan})

    assertContains(response, 'Committed')
    push_rollback.assert_called_once_with(backup, SEND)
    assert Backup.objects.get(reason='pre-rollback').content == RUNNING


def test_rollback_apply_shows_device_error(user_client, backup, running):
    plan = user_client.get(f'/rollback/{backup.pk}/').context['plan']
    error = DeviceError('172.21.20.11: config changed since the preview, preview again')
    with patch('operations.services.push_rollback', side_effect=error):
        response = user_client.post('/rollback/apply/', {'plan': plan})
    assertContains(response, 'config changed since the preview')
    assert not Backup.objects.filter(reason='pre-rollback').exists()


def test_rollback_apply_rejects_changed_plan(user_client, backup, running, push_rollback):
    plan = user_client.get(f'/rollback/{backup.pk}/').context['plan']
    # Keep the signature, empty the commands in the content
    signature = plan.rsplit(':', 1)[1]
    evil = signing.dumps({'backup': backup.pk, 'send': []}, salt=ROLLBACK_SALT)
    forged = evil.rsplit(':', 1)[0] + ':' + signature

    assert user_client.post('/rollback/apply/', {'plan': forged}).status_code == 400
    push_rollback.assert_not_called()


def test_rollback_apply_rejects_deploy_plan(user_client, backup, push_rollback):
    plan = signing.dumps({'backup': backup.pk, 'send': SEND}, salt=DEPLOY_SALT)
    assert user_client.post('/rollback/apply/', {'plan': plan}).status_code == 400
    push_rollback.assert_not_called()
