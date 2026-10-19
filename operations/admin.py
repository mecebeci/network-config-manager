from django.contrib import admin

from .models import Backup


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ['device', 'created_at', 'reason', 'created_by']
    list_filter = ['reason', 'device']

    # A backup is a copy of what was on the device; it is only created by
    # the app and never edited, otherwise a rollback could push fake config
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
