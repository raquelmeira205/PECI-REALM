from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    gdpr_consent = forms.BooleanField(
        required=True,
        label="Aceito os termos de processamento de dados sensíveis (RGPD)",
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-emerald-600 border-slate-300 rounded focus:ring-emerald-500'})
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'role', 'birth_date')
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

        