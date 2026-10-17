from django import forms

from devices.models import Device


class BackupForm(forms.Form):
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={'required': 'Select at least one device.'},
    )
