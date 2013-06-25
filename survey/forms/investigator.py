from django import forms
from survey.models import *
from django.forms import ModelForm
from django.core.validators import *

class InvestigatorForm(ModelForm):

    confirm_mobile_number = forms.CharField( widget=forms.TextInput(attrs={'placeholder': 'Format: 771234567',
                                                                            'style':"width:172px;" , 'maxlength':'10', 'type':'number'}))
    def __init__(self, *args, **kwargs):
        super(InvestigatorForm, self).__init__(*args, **kwargs)
        self.fields.keyOrder=['name', 'mobile_number', 'confirm_mobile_number', 'male', 'age', 'level_of_education', 'language', 'location']


    def clean(self):
        cleaned_data = super(InvestigatorForm, self).clean()
        mobile_number = cleaned_data.get("mobile_number")
        confirm_mobile_number = cleaned_data.get("confirm_mobile_number")

        if mobile_number != confirm_mobile_number:
            message = "Mobile numbers don't match."
            self._errors["confirm_mobile_number"] = self.error_class([message])
            raise forms.ValidationError(message)

        return cleaned_data

    class Meta:
        model = Investigator
        fields = ['name', 'mobile_number', 'male', 'age', 'level_of_education', 'language', 'location']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Name'}),
            'mobile_number': forms.TextInput(attrs={'placeholder': 'Format: 771234567', 'style':"width:172px;", 'maxlength':'10', 'type':'number'}),
            'male': forms.RadioSelect(choices=((True, 'Male'), (False, 'Female'))),
            'age': forms.TextInput(attrs={'placeholder': 'Age', 'min':18, 'max':50, 'type':'number' }),
            'location':forms.HiddenInput(),
        }
