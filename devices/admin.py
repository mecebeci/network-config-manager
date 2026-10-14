from django.contrib import admin

from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['name', 'ip', 'role', 'description']
    list_filter = ['role']
    search_fields = ['name', 'ip', 'description']
