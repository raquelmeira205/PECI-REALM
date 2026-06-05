from django import forms


class StartCaptureForm(forms.Form):
    name = forms.CharField(
        max_length=255,
        label='Nome da Captura',
        widget=forms.TextInput(attrs={
            'placeholder': 'Ex: Captura Pesquisa 2026-05',
            'class': 'w-full rounded-xl border-slate-300 focus:border-emerald-500 focus:ring-emerald-500 px-4 py-3',
        })
    )
