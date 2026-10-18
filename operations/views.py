from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from devices.models import Device
from network.rendering import RenderError

from . import services
from .forms import BackupForm, DeployForm
from .models import Backup


# ---------------------------------------------------------------------------
# Backup: taking backups
# ---------------------------------------------------------------------------

@login_required
def backup_page(request):
    # ?select=all|spine|leaf pre-ticks those devices; anything else ticks none
    select = request.GET.get('select')
    if select == 'all':
        initial = Device.objects.all()
    elif select in Device.Role.values:
        initial = Device.objects.filter(role=select)
    else:
        initial = []
    return render(request, 'operations/backup.html', {
        'form': BackupForm(initial={'devices': initial}),
        'roles': Device.Role.choices,
    })


@login_required
@require_POST
def backup_run(request):
    """htmx endpoint: returns only the results fragment, not a full page."""
    form = BackupForm(request.POST)
    if not form.is_valid():
        return render(request, 'operations/_backup_results.html', {'form': form})
    results = services.take_backups(
        form.cleaned_data['devices'], Backup.Reason.MANUAL, request.user,
    )
    return render(request, 'operations/_backup_results.html', {'results': results})

# --- end: taking backups ---


# ---------------------------------------------------------------------------
# Backup: viewing backups
# ---------------------------------------------------------------------------

@login_required
def device_backups(request, pk):
    device = get_object_or_404(Device, pk=pk)
    return render(request, 'operations/device_backups.html', {
        'device': device,
        'backups': device.backups.all(),
    })


@login_required
def backup_detail(request, pk):
    backup = get_object_or_404(Backup, pk=pk)
    return render(request, 'operations/backup_detail.html', {'backup': backup})


@login_required
def backup_download(request, pk):
    backup = get_object_or_404(Backup, pk=pk)
    filename = f'{backup.device.name}_{backup.created_at:%Y%m%d-%H%M%S}.cfg'
    return HttpResponse(backup.content, content_type='text/plain; charset=utf-8', headers={
        'Content-Disposition': content_disposition_header(as_attachment=True, filename=filename),
    })

# --- end: viewing backups ---


# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------

# Keeps a deploy signature from being valid anywhere else signing is used
DEPLOY_SALT = 'operations.deploy'


@login_required
def deploy_page(request):
    return render(request, 'operations/deploy.html', {'form': DeployForm()})


@login_required
def deploy_form(request):
    """htmx endpoint: the variable fields of the chosen template."""
    form = DeployForm(template=request.GET.get('template'))
    return render(request, 'operations/_deploy_fields.html', {'form': form})


@login_required
@require_POST
def deploy_preview(request):
    """htmx endpoint: rendered config per device, plus the signed plan for Apply."""
    form = DeployForm(request.POST)
    if not form.is_valid():
        return render(request, 'operations/_deploy_preview.html', {'form': form})

    devices = form.cleaned_data['devices']
    template = form.cleaned_data['template']
    variables = form.variables()
    try:
        configs = services.render_configs(devices, template, variables)
    except RenderError as e:
        # Shown above the form like any other form error
        form.add_error(None, str(e))
        return render(request, 'operations/_deploy_preview.html', {'form': form})

    # Apply gets this plan back and trusts only its signature, never the form again
    plan = signing.dumps({
        'devices': [device.pk for device in devices],
        'template': template,
        'variables': variables,
    }, salt=DEPLOY_SALT)
    return render(request, 'operations/_deploy_preview.html', {
        'configs': configs.items(),
        'plan': plan,
    })


@login_required
@require_POST
def deploy_apply(request):
    """htmx endpoint: runs exactly the plan that was previewed."""
    try:
        plan = signing.loads(request.POST.get('plan', ''), salt=DEPLOY_SALT)
    # Only a hand-edited request gets here, never the normal page, so a plain 400 is enough
    except signing.BadSignature:
        return HttpResponseBadRequest('Invalid deploy plan.')

    devices = Device.objects.filter(pk__in=plan['devices'])
    try:
        results = services.deploy(devices, plan['template'], plan['variables'], request.user)
    # The template file changed or was removed after the preview
    except RenderError as e:
        return render(request, 'operations/_deploy_results.html', {'error': str(e)})
    return render(request, 'operations/_deploy_results.html', {'results': results})

# --- end: deploy ---
