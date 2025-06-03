from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib import messages
from django.http import HttpResponse
from io import TextIOWrapper
import csv
import io
from .forms import RegisterForm, CriteriaForm, CSVUploadForm, FrameworkForm
from .models import Criteria, Framework, FrameworkScore, UserProfile
from django.core.management.base import BaseCommand
from functools import wraps

# Decorator untuk membatasi akses admin saja
def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Cek apakah user adalah superuser atau staff
        if not (request.user.is_superuser or request.user.is_staff):
            messages.error(request, 'Anda tidak memiliki akses untuk melakukan aksi ini.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def login(request):
    if request.user.is_authenticated:
        # Jika user sudah login, cek apakah admin atau user biasa
        if request.user.is_staff:  # atau gunakan request.user.is_superuser untuk superadmin
            return redirect('dashboard')  # halaman khusus admin
        else:
            return redirect('dashboard_user')  # halaman khusus user biasa

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            messages.success(request, 'Login berhasil!')

            if user.is_staff:
                return redirect('dashboard')
            else:
                return redirect('dashboard_user')
        else:
            messages.error(request, 'Username atau password salah.')

    return render(request, 'registration/login.html')


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.get_or_create(user=user)
            messages.success(request, 'Registrasi berhasil! Silakan login.')
            return redirect('login')  # arahkan ke halaman login
        else:
            messages.error(request, 'Terjadi kesalahan pada form registrasi.')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'Anda telah logout.')
    return redirect('login')

# Dashboard
@login_required
def dashboard(request):
    # Statistik dasar
    total_frameworks = Framework.objects.count()
    total_criteria = Criteria.objects.count()
    total_weight = sum(c.weight for c in Criteria.objects.all())
    
    context = {
        'total_frameworks': total_frameworks,
        'total_criteria': total_criteria,
        'total_weight': total_weight,
        'is_ready_to_calculate': abs(total_weight - 1.0) < 0.001 and total_frameworks > 0
    }
    return render(request, 'dashboard.html', context)

@login_required
def dashboard_user(request):
    criteria = Criteria.objects.all()
    total_frameworks = Framework.objects.count()
    total_criteria = Criteria.objects.count()
    total_weight = sum(c.weight for c in Criteria.objects.all())
    
    context = {
        'criteria': criteria,
        'total_frameworks': total_frameworks,
        'total_criteria': total_criteria,
        'total_weight': total_weight,
        'is_ready_to_calculate': abs(total_weight - 1.0) < 0.001 and total_frameworks > 0
    }
    return render(request, 'user/dashboard_user.html', context)

# Criteria Management
def criteria_list_view(request):
    criteria_list = Criteria.objects.all()

    # Hitung total bobot kriteria
    total_weight = sum(c.weight for c in criteria_list)

    context = {
        'criteria_list': criteria_list,
        'total_weight': total_weight,
    }
    return render(request, 'user/criteria_list_user.html', context)

@login_required
def framework_list_user(request):
    criteria_list = Criteria.objects.all()
    frameworks = Framework.objects.all()
    total_frameworks = frameworks.count()
    total_criteria = criteria_list.count()
    total_weight = sum(c.weight for c in criteria_list)
    
    # Siapkan data untuk tabel dengan scores
    framework_data = []
    for fw in frameworks:
        fw_scores = {}
        for criteria in criteria_list:
            score = FrameworkScore.objects.filter(framework=fw, criteria=criteria).first()
            fw_scores[criteria.id] = score.value if score else 0
        
        framework_data.append({
            'framework': fw,
            'scores': fw_scores
        })
    
    return render(request, 'user/framework_list_user.html', {
        'framework_data': framework_data,
        'criteria_list': criteria_list,
        'total_weight': total_weight,
        'total_frameworks': total_frameworks,
        'total_criteria': total_criteria,
        'is_ready': len(frameworks) > 0
    })



@login_required
def add_criteria(request):
    if request.method == 'POST':
        form = CriteriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Kriteria "{form.cleaned_data["name"]}" berhasil ditambahkan.')
            return redirect('framework_list')
        else:
            messages.error(request, 'Terjadi kesalahan saat menambah kriteria.')
    else:
        form = CriteriaForm()
    return render(request, 'criteria_form.html', {'form': form})

@login_required
def criteria_list(request):
    criteria = Criteria.objects.all()
    return render(request, 'criteria_list.html', {'criteria_list': criteria})

@login_required
def edit_criteria(request, criteria_id):
    criteria = get_object_or_404(Criteria, id=criteria_id)
    if request.method == 'POST':
        form = CriteriaForm(request.POST, instance=criteria)
        if form.is_valid():
            form.save()
            messages.success(request, f'Kriteria "{criteria.name}" berhasil diperbarui.')
            return redirect('framework_list')
    else:
        form = CriteriaForm(instance=criteria)
    return render(request, 'criteria_form.html', {'form': form, 'edit_mode': True})

@login_required
def delete_criteria(request, criteria_id):
    criteria = get_object_or_404(Criteria, id=criteria_id)
    if request.method == 'POST':
        criteria_name = criteria.name
        criteria.delete()
        messages.success(request, f'Kriteria "{criteria_name}" berhasil dihapus.')
    return redirect('framework_list')

#add framework user
@login_required
def add_framework_user(request):
    criteria_list = Criteria.objects.all()

    if request.method == 'POST':
        if 'csv_upload' in request.FILES:
            csv_file = request.FILES['csv_upload']
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "File harus format CSV.")
            else:
                file_data = TextIOWrapper(csv_file.file, encoding='utf-8-sig')
                reader = csv.DictReader(file_data, delimiter=';')
                count = 0

                for row in reader:
                    row = {k.strip(): v for k, v in row.items()}
                    name = row.get('name')
                    description = row.get('description')
                    performa = row.get('Performa')
                    skalabilitas = row.get('Skalabilitas')
                    komunitas = row.get('Komunitas')
                    kemudahanBelajar = row.get('Kemudahan Belajar')
                    pemeliharaan = row.get('Pemeliharaan & Update')

                    if not name:
                        continue

                    framework = Framework.objects.create(
                        name=name,
                        description=description,
                        community=komunitas,
                        learning_time=kemudahanBelajar,
                        maintenance=pemeliharaan,
                        performance=performa,
                        scalability=skalabilitas
                    )

                    # Simpan nilai kriteria
                    for criteria in criteria_list:
                        score_val = row.get(criteria.name)
                        try:
                            score_val = float(score_val) if score_val else None
                        except ValueError:
                            score_val = None

                        if score_val is not None:
                            FrameworkScore.objects.create(
                                framework=framework,
                                criteria=criteria,
                                value=score_val
                            )

                    count += 1

                messages.success(request, f'{count} framework berhasil diimport oleh user.')
                return redirect('framework_list_user')
        else:
            messages.error(request, "Silakan upload file CSV.")
    
    return render(request, 'user/framework_form.html', {
        'criteria_list': criteria_list
    })

@login_required
def add_framework(request):
    criteria_list = Criteria.objects.all()

    if request.method == 'POST':
        # Cek apakah upload CSV atau form biasa
        if 'csv_upload' in request.FILES:
            csv_file = request.FILES['csv_upload']
            # Pastikan file csv (optional)
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "File harus format CSV.")
            else:
                # Decode dan baca CSV
                file_data = TextIOWrapper(csv_file.file, encoding='utf-8-sig')
                reader = csv.DictReader(file_data, delimiter=';')

                count = 0
                for row in reader:
                    row = {k.strip(): v for k, v in row.items()}
                    # Asumsi kolom CSV: name, description, score_<criteria_id> ...
                    name = row.get('name')
                    description = row.get('description')
                    performa = row.get('Performa')
                    skalabilitas = row.get('Skalabilitas')
                    komunitas = row.get('Komunitas')
                    kemudahanBelajar = row.get('Kemudahan Belajar')
                    pemeliharaan = row.get('Pemeliharaan & Update')

                    if not name:
                        continue  # skip jika nama kosong
                

                    # Simpan framework (bisa ada duplikat)
                    framework = Framework.objects.create(
                        name=name,
                        description=description,
                        community=komunitas,
                        learning_time=kemudahanBelajar,
                        maintenance=pemeliharaan,
                        performance=performa,
                        scalability=skalabilitas
                    )
                    
                    form = FrameworkForm(request.POST)
                    if form.is_valid():
                        name = form.cleaned_data['name']
                        if Framework.objects.filter(name=name).exists():
                            messages.error(request, f'Framework "{name}" sudah ada.')
                        else:
                            framework = form.save()
                    # Simpan nilai untuk tiap criteria
                    for criteria in criteria_list:
                        score_val = row.get(criteria.name)
                        try:
                            score_val = float(score_val) if score_val else None
                        except ValueError:
                            score_val = None

                        if score_val is not None:
                            FrameworkScore.objects.create(
                                framework=framework,
                                criteria=criteria,
                                value=score_val
                                )
                    count += 1
                messages.success(request, f'{count} framework berhasil diimport dari CSV.')
                return redirect('framework_list')

        else:
            form = FrameworkForm(request.POST)
            if form.is_valid():
                fw = form.save()
                for crit in criteria_list:
                    nilai = request.POST.get(f'score_{crit.id}')
                    if nilai:
                        try:
                            value = float(nilai)
                            FrameworkScore.objects.update_or_create(
                                framework=fw,
                                criteria=crit,
                                defaults={'value': value}
                                )
                        except ValueError:
                            continue
                messages.success(request, f'Framework "{fw.name}" berhasil ditambahkan.')
                return redirect('framework_list')
            else:
                messages.error(request, "Form tidak valid.")
    else:
        form = FrameworkForm()
        
    return render(request, 'framework_form.html', {
                  'form': form,
                  'criteria_list': criteria_list,
    })


@login_required
def edit_framework_scores(request, framework_id):
    framework = get_object_or_404(Framework, id=framework_id)
    criteria_list = Criteria.objects.all()

    # Ambil nilai existing jadi dict {criteria.id: value}
    existing = FrameworkScore.objects.filter(framework=framework)
    scores = {s.criteria.id: s.value for s in existing}

    if request.method == 'POST':
        for criteria in criteria_list:
            key = f'score_{criteria.id}'
            if key in request.POST:
                raw = request.POST[key]
                try:
                    FrameworkScore.objects.update_or_create(
                        framework=framework,
                        criteria=criteria,
                        defaults={'value': float(raw)}
                    )
                except ValueError:
                    messages.error(request, f'Nilai tidak valid untuk kriteria {criteria.name}')
        messages.success(request, f'Skor untuk "{framework.name}" berhasil diperbarui.')
        return redirect('framework_list')

    return render(request, 'edit_frameworks_scores.html', {
        'framework': framework,
        'criteria_list': criteria_list,
        'scores': scores,  # di template: value="{{ scores|lookup:criteria.id }}"
    })
    
@login_required
def delete_framework(request, framework_id):
    framework = get_object_or_404(Framework, id=framework_id)
    if request.method == 'POST':
        framework.delete()
        messages.success(request, f'Framework "{framework.name}" berhasil dihapus.')
        return redirect('framework_list')
    # Kalau mau tampilkan konfirmasi sebelum delete:
    return render(request, 'framework_delete.html', {
        'framework': framework
    })
# Framework List
@login_required
def framework_list(request):
    criteria_list = Criteria.objects.all()
    frameworks = Framework.objects.all()
    total_weight = sum(c.weight for c in criteria_list)
    
    # Siapkan data untuk tabel dengan scores
    framework_data = []
    for fw in frameworks:
        fw_scores = {}
        for criteria in criteria_list:
            score = FrameworkScore.objects.filter(framework=fw, criteria=criteria).first()
            fw_scores[criteria.id] = score.value if score else 0
        
        framework_data.append({
            'framework': fw,
            'scores': fw_scores
        })
    
    return render(request, 'framework_list.html', {
        'framework_data': framework_data,
        'criteria_list': criteria_list,
        'total_weight': total_weight,
        'is_ready': len(frameworks) > 0
    })
    

@login_required
def calculate_saw(request):
    # Ambil semua kriteria dan framework
    criteria_list = list(Criteria.objects.all())
    frameworks   = list(Framework.objects.all())

    # Validasi data
    if not criteria_list or not frameworks:
        messages.error(request, 'Data kriteria atau framework masih kosong.')
        return redirect('framework_list')

    # Total bobot harus 1.0
    total_weight = sum(c.weight for c in criteria_list)
    if abs(total_weight - 1.0) > 0.001:
        messages.error(request, f'Total bobot kriteria harus 1.0 (saat ini: {total_weight:.3f}).')
        return redirect('framework_list')

    # 1. Bangun matriks X dan cari max/min per kriteria
    raw_values = {}  # {fw.id: {c.id: value, ...}, ...}
    max_vals   = {}
    min_vals   = {}

    # Inisialisasi max/min
    for c in criteria_list:
        max_vals[c.id] = 0
        min_vals[c.id] = float('inf')

    # Isi raw_values dan update max/min
    for fw in frameworks:
        vals = {}
        for c in criteria_list:
            fs = FrameworkScore.objects.filter(framework=fw, criteria=c).first()
            x = fs.value if fs and fs.value is not None else 0.0
            vals[c.id] = x

            if x > max_vals[c.id]:
                max_vals[c.id] = x
            if x < min_vals[c.id]:
                min_vals[c.id] = x
        raw_values[fw.id] = vals

    # Jika semua nilai kriteria nol, atur min=0, max=1 agar tidak div/0
    for c in criteria_list:
        if max_vals[c.id] == 0:
            max_vals[c.id] = 1
        if min_vals[c.id] == float('inf'):
            min_vals[c.id] = 0

    # 2. Normalisasi R dan hitung skor V
    final_scores = []  # list of dict {framework, score, score_display, percentage, rank, medal}

    for fw in frameworks:
        total_score = 0.0
        for c in criteria_list:
            x = raw_values[fw.id][c.id]
            if c.attribute == 'benefit':
                # Benefit: x / max
                r = x / max_vals[c.id] if max_vals[c.id] > 0 else 0
            else:
                # Cost: min / x
                r = (min_vals[c.id] / x) if x > 0 else 0

            total_score += r * c.weight

        final_scores.append({
            'framework': fw.name,
            'score': total_score,
            'score_display': round(total_score, 6),
            'percentage': round(total_score * 100, 2),
        })

    # 3. Urutkan berdasarkan score dan beri peringkat/medali
    final_scores.sort(key=lambda d: d['score'], reverse=True)
    for idx, item in enumerate(final_scores, start=1):
        item['rank'] = idx
        if idx == 1:
            item['medal'] = '🥇'
        elif idx == 2:
            item['medal'] = '🥈'
        elif idx == 3:
            item['medal'] = '🥉'
        else:
            item['medal'] = ''

    # Framework terbaik
    best_framework = final_scores[0] if final_scores else None

    return render(request, 'result.html', {
        'criteria_list': criteria_list,
        'final_scores': final_scores,
        'best_framework': best_framework,
    })


@login_required
def upload_csv(request):
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            
            try:
                # Read & decode
                file_data = csv_file.read().decode('utf-8')
                io_string = io.StringIO(file_data)
                reader = csv.DictReader(io_string)
                
                # --- normalize headers: strip spaces off each fieldname ---
                if reader.fieldnames:
                    reader.fieldnames = [h.strip() for h in reader.fieldnames]
                
                filename = csv_file.name.lower()
                
                # 1) Upload criteria
                if 'criteria' in filename:
                    expected = ['name', 'weight', 'attribute']
                    missing = [c for c in expected if c not in reader.fieldnames]
                    if missing:
                        messages.error(request, f'Kolom criteria hilang: {", ".join(missing)}')
                        return redirect('framework_list')

                    success_count = 0
                    for idx, row in enumerate(reader, start=1):
                        try:
                            Criteria.objects.update_or_create(
                                name=row['name'].strip(),
                                defaults={
                                    'weight': float(row['weight']),
                                    'attribute': row['attribute'].strip().lower()
                                }
                            )
                            success_count += 1
                        except Exception as e:
                            messages.warning(request,
                                             f'Error di baris {idx} (criteria): {e}'
                                             )
                    messages.success(request, f'{success_count} kriteria berhasil diupload.')
                
                # 2) Upload framework & scores (data)
                file_data = csv_file.read().decode('utf-8')
                io_string = io.StringIO(file_data)
                reader = csv.DictReader(io_string, delimiter='\t')  # <-- penting, sesuaikan delimiter
                if reader.fieldnames:
                    reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
                    
                elif 'framework' in filename or 'data' in filename:
                    expected = [
                        'Framework',
                        'Deskripsi',
                        'Performa (req/s)',
                        'Skalabilitas (1-5)',
                        'Komunitas (User)',
                        'Kemudahan Belajar (Jam)',
                        'Pemeliharaan & Update (per Tahun)'
                    ]
                    missing = [c for c in expected if c not in reader.fieldnames]
                    if missing:
                        messages.error(request,
                                       f'Kolom data hilang: {", ".join(missing)}'
                                       )
                        return redirect('framework_list')

                    row_count = 0
                    score_count = 0

                    column_mapping = {
                        'Performa (req/s)': 'Performa',
                        'Skalabilitas (1-5)': 'Skalabilitas',
                        'Komunitas (User)': 'Komunitas',
                        'Kemudahan Belajar (Jam)': 'Kemudahan Belajar',
                        'Pemeliharaan & Update (per Tahun)': 'Pemeliharaan & Update',
                    }

                    for row in reader:
                        name = row.get('Framework', '').strip()
                        if not name:
                            continue
                        row_count += 1

                        framework, created = Framework.objects.get_or_create(
                            name=name,
                            defaults={'description': f'Framework {name}'}
                        )

                        for csv_col, crit_name in column_mapping.items():
                            raw = row.get(csv_col, '').strip()
                            if not raw:
                                continue
                            try:
                                val = float(raw)
                            except ValueError:
                                messages.warning(
                                    request,
                                    f'Nilai tidak valid di kolom "{csv_col}", baris {row_count}: "{raw}"'
                                )
                                continue

                            crit = Criteria.objects.filter(name=crit_name).first()
                            if not crit:
                                messages.warning(
                                    request,
                                    f'Criteria "{crit_name}" tidak ditemukan (baris {row_count}).'
                                )
                                continue

                            FrameworkScore.objects.update_or_create(
                                framework=framework,
                                criteria=crit,
                                defaults={'value': val}
                            )
                            score_count += 1

                    messages.success(
                        request,
                        f'{row_count} baris framework diproses (baru maupun update).'
                    )
                    if score_count:
                        messages.success(
                            request,
                            f'{score_count} skor berhasil diupload.'
                        )
                    else:
                        messages.info(
                            request,
                            'Tidak ada skor yang diupload.'
                        )

                # 3) Upload khusus score saja
                elif 'score' in filename:
                    expected = ['framework', 'criteria', 'value']
                    missing = [c for c in expected if c not in reader.fieldnames]
                    if missing:
                        messages.error(request,
                                       f'Kolom score hilang: {", ".join(missing)}'
                                       )
                        return redirect('framework_list')

                    success_count = 0
                    for idx, row in enumerate(reader, start=1):
                        try:
                            fw = Framework.objects.get(name=row['framework'].strip())
                            crit = Criteria.objects.get(name=row['criteria'].strip())
                            val = float(row['value'])
                            FrameworkScore.objects.update_or_create(
                                framework=fw,
                                criteria=crit,
                                defaults={'value': val}
                            )
                            success_count += 1
                        except Framework.DoesNotExist:
                            messages.warning(request,
                                             f'Framework "{row.get("framework")}" tidak ditemukan (baris {idx}).'
                                             )
                        except Criteria.DoesNotExist:
                            messages.warning(request,
                                             f'Criteria "{row.get("criteria")}" tidak ditemukan (baris {idx}).'
                                             )
                        except Exception as e:
                            messages.warning(request,
                                             f'Error di baris {idx} (score): {e}'
                                             )
                    messages.success(request, f'{success_count} score berhasil diupload.')

                else:
                    messages.error(
                        request,
                        'Nama file harus mengandung "criteria", "framework", "data", atau "score".'
                    )

                return redirect('framework_list')

            except Exception as e:
                messages.error(request, f'Error membaca file CSV: {e}')
                return redirect('framework_list')
    else:
        form = CSVUploadForm()

    upload_guide = {
        'criteria': {
            'filename': 'criteria.csv',
            'columns': ['name', 'weight', 'attribute'],
            'example': 'Performa,0.25,benefit'
        },
        'framework': {
            'filename': 'data.csv atau framework_data.csv',
            'columns': [
                'Framework',
                'Performa (req/s)',
                'Skalabilitas (1-5)',
                'Komunitas (User)',
                'Kemudahan Belajar (Jam)',
                'Pemeliharaan & Update (per Tahun)'
            ],
            'example': 'React,8500,4,500000,40,12'
        }
    }

    return render(request, 'upload_csv.html', {
        'form': form,
        'upload_guide': upload_guide
    })

# Management Command untuk import data
class Command(BaseCommand):  
    help = "Import criteria & framework data from CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            '--criteria-csv', required=True,
            help="Path to criteria.csv (name,weight,attribute)"
        )
        parser.add_argument(
            '--data-csv', required=True,
            help="Path to data.csv with framework metrics"
        )

    def handle(self, *args, **options):
        criteria_csv = options['criteria_csv']
        data_csv = options['data_csv']

        # 1. Reset & load kriteria
        self.stdout.write("🔄 Resetting Criteria...")
        Criteria.objects.all().delete()
        
        with open(criteria_csv, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                Criteria.objects.create(
                    name=row['name'].strip(),
                    weight=float(row['weight']),
                    attribute=row['attribute'].strip().lower()
                )
        
        all_criteria = list(Criteria.objects.all())
        self.stdout.write(f"✔️ Loaded {len(all_criteria)} criteria.")

        # 2. Load data.csv dan mapping kolom ke nama kriteria
        mapping = {
            'Performa (req/s)': 'Performa',
            'Skalabilitas (1-5)': 'Skalabilitas',
            'Komunitas (User)': 'Komunitas',
            'Kemudahan Belajar (Jam)': 'Kemudahan Belajar',
            'Pemeliharaan & Update (per Tahun)': 'Pemeliharaan & Update',
        }

        self.stdout.write("🔄 Processing data.csv for frameworks & scores...")
        created_fw = 0
        updated_scores = 0
        
        with open(data_csv, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=',')
            for row in reader:
                # Skip empty rows
                if not row.get('Framework') or row.get('Framework').strip() == '':
                    continue
                    
                fw_name = row['Framework'].strip()
                
                # 3. Create or get Framework
                fw, created = Framework.objects.get_or_create(
                    name=fw_name,
                    defaults={'description': f'Framework {fw_name}'}
                )
                if created:
                    created_fw += 1

                # 4. For each mapped kriteria, update or create score
                for col, crit_name in mapping.items():
                    raw_val = row.get(col)
                    if raw_val is None or raw_val == '':
                        continue
                    try:
                        value = float(raw_val)
                    except ValueError:
                        continue

                    crit = next((c for c in all_criteria if c.name == crit_name), None)
                    if not crit:
                        self.stderr.write(f"⚠️ Criteria '{crit_name}' not found, skipping.")
                        continue

                    FrameworkScore.objects.update_or_create(
                        framework=fw,
                        criteria=crit,
                        defaults={'value': value}
                    )

                    updated_scores += 1

        self.stdout.write(f"✔️ Created {created_fw} new frameworks.")
        self.stdout.write(f"✔️ Updated/Created {updated_scores} framework scores.")
        

@login_required
def export_data(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="framework_scores.csv"'

    writer = csv.writer(response)
    criteria = Criteria.objects.all()
    headers = ['Framework'] + [c.name for c in criteria]
    writer.writerow(headers)

    frameworks = Framework.objects.all()
    for fw in frameworks:
        row = [fw.name]
        for c in criteria:
            score = FrameworkScore.objects.filter(framework=fw, criteria=c).first()
            row.append(score.value if score else '')
        writer.writerow(row)

    return response

@login_required
def reset_data(request):
    FrameworkScore.objects.all().delete()
    Framework.objects.all().delete()
    messages.success(request, "Semua data framework dan skor berhasil di-reset.")
    return redirect('framework_list')

def download_csv_template(request):
    # contoh response CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="template.csv"'
    response.write("name,description\n")  # contoh header kolom
    return response