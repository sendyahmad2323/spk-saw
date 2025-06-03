from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Criteria, Framework, FrameworkScore
from django.core.exceptions import ValidationError
import csv
import io

class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})

class CriteriaForm(forms.ModelForm):
    class Meta:
        model = Criteria
        fields = ['name', 'weight', 'attribute']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan nama kriteria'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '1',
                'placeholder': '0.00'
            }),
            'attribute': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight is not None and (weight <= 0 or weight > 1):
            raise forms.ValidationError('Bobot harus antara 0.01 sampai 1.0')
        return weight

        
class FrameworkForm(forms.ModelForm):
    class Meta:
        model = Framework
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nama framework (contoh: Django, Flask, FastAPI)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Deskripsi singkat tentang framework ini...'
            }),
        }
        

    def clean(self):
        cleaned_data = super().clean()
        for field in ['performa', 'skalabilitas', 'komunitas', 'kemudahan_belajar', 'pemeliharaan']:
            value = cleaned_data.get(field)
            if value is not None and (value < 1 or value > 10):
                self.add_error(field, 'Nilai harus antara 1 dan 10')

class FrameworkScoreForm(forms.ModelForm):
    class Meta:
        model = FrameworkScore
        fields = ['framework', 'criteria', 'value']
        widgets = {
            'framework': forms.Select(attrs={'class': 'form-select'}),
            'criteria': forms.Select(attrs={'class': 'form-select'}),
            'value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
        }


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label='Pilih file CSV',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv',
        }),
        help_text='Format file: criteria.csv, frameworks.csv, atau scores.csv'
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        if not csv_file.name.endswith('.csv'):
            raise ValidationError('File harus berformat CSV (.csv)')
        
        if csv_file.size > 5 * 1024 * 1024:  # 5MB limit
            raise ValidationError('Ukuran file terlalu besar. Maksimal 5MB.')
        
        # Validate CSV content
        try:
            csv_file.seek(0)
            content = csv_file.read().decode('utf-8')
            csv_file.seek(0)  # Reset file pointer
            
            # Check if file has content
            if not content.strip():
                raise ValidationError('File CSV kosong.')
            
            # Basic CSV validation
            reader = csv.reader(io.StringIO(content))
            headers = next(reader, None)
            
            if not headers:
                raise ValidationError('File CSV tidak memiliki header.')
            
            expected_headers = ['nama', 'deskripsi', 'performa', 'skalabilitas', 'komunitas', 'kemudahan_belajar', 'pemeliharaan']
            headers_lower = [h.lower().strip() for h in headers]
            
            if headers_lower[:2] != ['nama', 'deskripsi']:  # At least nama and deskripsi required
                raise ValidationError('Header CSV harus dimulai dengan: nama,deskripsi,...')
                
        except UnicodeDecodeError:
            raise ValidationError('File tidak dapat dibaca. Pastikan encoding UTF-8.')
        except Exception as e:
            raise ValidationError(f'Error membaca file CSV: {str(e)}')
        return csv_file
