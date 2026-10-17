from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from devices.models import Device

from . import services
from .forms import BackupForm
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
