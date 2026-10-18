import pytest
from django.core import signing
from pytest_django.asserts import assertContains, assertNotContains, assertRedirects

from operations.models import Backup
from operations.views import DEPLOY_SALT

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
