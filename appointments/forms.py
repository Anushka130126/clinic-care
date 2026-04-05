from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import PatientProfile

class PatientRegistrationForm(UserCreationForm):
    """Custom form to force Email and Phone Number collection during signup"""
    email = forms.EmailField(required=True, help_text="Required for mock email notifications.")
    phone_number = forms.CharField(max_length=15, required=True, help_text="Required for mock SMS notifications.")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)

    def save(self, commit=True):
        # 1. Save the User account with the email
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']

        if commit:
            user.save()
            # 2. Automatically generate the Profile with the phone number
            PatientProfile.objects.create(
                user=user,
                phone_number=self.cleaned_data['phone_number']
            )
        return user