from django.db import models


class Device(models.Model):
    class Role(models.TextChoices):
        SPINE = 'spine', 'Spine'
        LEAF = 'leaf', 'Leaf'

    name = models.CharField(max_length=64, unique=True)
    ip = models.GenericIPAddressField(unique=True)
    role = models.CharField(max_length=16, choices=Role.choices)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
