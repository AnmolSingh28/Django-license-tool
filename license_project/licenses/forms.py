# forms.py
from django import forms

class LicenseRequestForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    product = forms.CharField(max_length=100)
