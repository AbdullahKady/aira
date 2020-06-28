from django import forms
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from captcha.fields import CaptchaField
from geowidgets import LatLonField
from registration.forms import RegistrationForm

from .models import Agrifield, AppliedIrrigation, Profile


class ProfileForm(forms.ModelForm):
    supervisor = forms.ModelChoiceField(
        queryset=User.objects.filter(profile__supervision_question=True), required=False
    )

    class Meta:
        model = Profile
        exclude = ("user",)

        labels = {
            "first_name": _("Given name"),
            "last_name": _("Family name"),
            "address": _("Address"),
            "notification": _("Frequency of email notifications"),
            "email_language": _("Email notification language"),
            "supervisor": _("Supervisor"),
            "supervision_question": _("Consider me as supervisor for other accounts"),
        }


class AgrifieldForm(forms.ModelForm):
    location = LatLonField(
        label=_("Co-ordinates"),
        help_text=_("Longitude and latitude in decimal degrees"),
    )

    class Meta:
        model = Agrifield
        exclude = ("owner",)
        fields = [
            "name",
            "area",
            "location",
            "crop_type",
            "irrigation_type",
            "is_virtual",
            "use_custom_parameters",
            "custom_irrigation_optimizer",
            "custom_root_depth_max",
            "custom_root_depth_min",
            "custom_max_allowed_depletion",
            "custom_efficiency",
            "custom_field_capacity",
            "custom_thetaS",
            "custom_wilting_point",
            "soil_analysis",
        ]

        labels = {
            "name": _("Field name"),
            "is_virtual": _("Is this a virtual field?"),
            "location": _("Co-ordinates"),
            "crop_type": _("Crop type"),
            "irrigation_type": _("Irrigation type"),
            "area": _("Irrigated area (m²)"),
            "use_custom_parameters": _("Use custom parameters"),
            "custom_irrigation_optimizer": _("Irrigation optimizer"),
            "custom_root_depth_max": _("Estimated root depth (max)"),
            "custom_root_depth_min": _("Estimated root depth (min)"),
            "custom_max_allowed_depletion": _("Maximum allowed depletion"),
            "custom_efficiency": _("Irrigation efficiency"),
            "custom_field_capacity": _("Field capacity"),
            "custom_thetaS": _("Soil moisture at saturation"),
            "custom_wilting_point": _("Permanent wilting point"),
            "soil_analysis": _("Soil analysis document"),
        }

    def clean(self):
        cleaned_data = super(AgrifieldForm, self).clean()
        is_virtual = cleaned_data.get("is_virtual")

        if is_virtual is None:
            msg = _("You must select if field is virtual or not")
            self.add_error("is_virtual", msg)


class AppliedIrrigationForm(forms.ModelForm):
    LABLED_IRRIGATION_TYPES = [
        ("VOLUME_OF_WATER", _("I want to specify the volume of water")),
        ("DURATION_OF_IRRIGATION", _("I want to specify the duration of irrigation")),
        ("FLOWMETER_READINGS", _("I want to register the flowmeter readings")),
    ]
    irrigation_type = forms.ChoiceField(
        widget=forms.RadioSelect(), choices=LABLED_IRRIGATION_TYPES, label=""
    )

    class Meta:
        model = AppliedIrrigation
        exclude = ("agrifield",)
        labels = {
            "timestamp": _("Date and time (YYYY-MM-DD HH:mm:ss) "),
            "supplied_water_volume": _("Volume of applied irrigation water (m³)"),
            "supplied_duration": _("Duration of irrigation (min)"),
            "supplied_flow_rate": _("Flow rate (m³/h)"),
            "flowmeter_reading_start": _("Flowmeter reading at start of irrigation"),
            "flowmeter_reading_end": _("Flowmeter reading at end of irrigation"),
            "flowmeter_water_percentage": _(
                "Percentage of water that corresponds to the flowmeter (%)"
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        irrigation_type = cleaned_data.get("irrigation_type")
        if irrigation_type == "VOLUME_OF_WATER":
            self._validate_required(["supplied_water_volume"])
        elif irrigation_type == "DURATION_OF_IRRIGATION":
            self._validate_required(["supplied_duration", "supplied_flow_rate"])
        elif irrigation_type == "FLOWMETER_READINGS":
            fields = [
                "flowmeter_reading_start",
                "flowmeter_reading_end",
                "flowmeter_water_percentage",
            ]
            self._validate_required(fields)
        return super().clean()

    def _validate_required(self, fields=[]):
        # Used to require fields dynamically (depending on other submitted values)
        for field in fields:
            if self.cleaned_data.get(field, None) is None:
                self.add_error(field, _("This field is required."))


class AgrifieldTelemetricFlowmeterForm(forms.ModelForm):
    """
    Since the flowmeter types are restricted to a single type for now, the form is
    static. Note that the "telemetric_flowmeter_details_fields" should change
    dynamically with the addition of new flowmeter types.
    """
    device_id = forms.CharField(max_length=64, strip=True, required=False)
    water_percentage = forms.IntegerField(min_value=0, max_value=100, required=False)

    def __init__(self, *args, **kwargs):
        self.telemetric_flowmeter_details_fields = ["device_id", "water_percentage"]
        # Provide initial values for fields nested in "telemetric_flowmeter_details"
        instance = kwargs.get("instance", None)
        if instance.telemetric_flowmeter_details:
            kwargs.update(initial=instance.telemetric_flowmeter_details)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("telemetric_flowmeter_type") == "LoRA_ARTA":
            self._validate_required(self.telemetric_flowmeter_details_fields)

        return super().clean()

    def clean_telemetric_flowmeter_details(self):
        return {k: self.data[k] for k in self.telemetric_flowmeter_details_fields}

    def _validate_required(self, fields=[]):
        for field in fields:
            if self.cleaned_data.get(field, None) is None:
                self.add_error(field, _("This field is required."))

    class Meta:
        model = Agrifield
        fields = [
            "telemetric_flowmeter_type",
            "telemetric_flowmeter_details",
            "device_id",
            "water_percentage",
        ]
        widgets = {"telemetric_flowmeter_details": forms.HiddenInput()}
        labels = {
            "telemetric_flowmeter_type": _("Telemetric system type"),
            "device_id": _("Device id"),
            "water_percentage": _(
                "Percentage of water that corresponds to the flowmeter (%)"
            ),
        }


class MyRegistrationForm(RegistrationForm):

    """
    Extension of the default registration form to include a captcha
    """

    captcha = CaptchaField(label=_("Are you human?"))
