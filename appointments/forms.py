from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import PatientProfile
from .models import DiagnosisReport

# --- 1. Edit Profile Forms ---
class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = PatientProfile
        fields = ['phone_number', 'medical_history']

# --- 2. New Registration Form ---
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


class DiagnosisForm(forms.ModelForm):
    """Form for doctors to write the medical report"""
    class Meta:
        model = DiagnosisReport
        fields = ['symptoms', 'diagnosis', 'prescription', 'notes']
        widgets = {
            'symptoms': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., Fever, headache for 3 days...'}),
            'diagnosis': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., Viral Pharyngitis...'}),
            'prescription': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., Paracetamol 500mg twice a day...'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Rest for 2 days, drink plenty of fluids.'}),
        }