from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Device


@login_required
def device_list(request):
    devices = Device.objects.all()
    role = request.GET.get('role')
    if role in Device.Role.values:
        devices = devices.filter(role=role)
    else:
        role = None
    return render(request, 'devices/device_list.html', {
        'devices': devices,
        'roles': Device.Role.choices,
        'current_role': role,
    })
