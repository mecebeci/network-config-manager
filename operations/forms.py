from django import forms

from devices.models import Device
from network import rendering

from .models import Backup

# Variable fields get this prefix so a template variable named 'devices'
# or 'template' cannot clash with the form's own fields
VAR_PREFIX = 'var_'


def device_choice_field():
    return forms.ModelMultipleChoiceField(
        queryset=Device.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={'required': 'Select at least one device.'},
    )


class BackupForm(forms.Form):
    devices = device_choice_field()


class CompareForm(forms.Form):
    """?a=<id>&b=<id>: a is the older side of the diff, b the newer."""

    a = forms.ModelChoiceField(queryset=Backup.objects.all())
    b = forms.ModelChoiceField(queryset=Backup.objects.all())


class DeployForm(forms.Form):
    """Devices + template, plus one text field per variable of the chosen template."""

    template = forms.ChoiceField()
    devices = device_choice_field()

    def __init__(self, *args, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        templates = rendering.list_templates()
        self.fields['template'].choices = [('', '---')] + [(t, t) for t in templates]

        # The template comes from the argument (GET /deploy/form/) or the POST data
        template = template or self.data.get('template')
        if template in templates:
            for name in rendering.user_variables(template):
                # Not required: an empty field means "use the template's default";
                # a variable without a default fails in render() with a clear message
                self.fields[VAR_PREFIX + name] = forms.CharField(label=name, required=False)

    def variable_fields(self):
        return [self[name] for name in self.fields if name.startswith(VAR_PREFIX)]

    def variables(self):
        """{'ntp_server': '10.0.0.1', ...} from cleaned_data, without the prefix."""
        return {
            name.removeprefix(VAR_PREFIX): value
            for name, value in self.cleaned_data.items()
            if name.startswith(VAR_PREFIX)
        }
