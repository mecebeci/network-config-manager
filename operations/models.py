from django.conf import settings
from django.db import models

from devices.models import Device


class Backup(models.Model):
    class Reason(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        PRE_DEPLOY = 'pre-deploy', 'Pre-deploy'
        PRE_ROLLBACK = 'pre-rollback', 'Pre-rollback'

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='backups')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=16, choices=Reason.choices)
    # Kept when the user is deleted: the backup is still valid history
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.device} @ {self.created_at:%Y-%m-%d %H:%M:%S}'
