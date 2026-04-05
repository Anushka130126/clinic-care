from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.db.models import Max, Count, Q
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from datetime import datetime, date
import csv

from .models import Doctor, Appointment, Token, TIME_SLOTS, PatientProfile
from .utils import send_mock_notification,recalculate_queue
from .forms import UserUpdateForm, ProfileUpdateForm

from django.contrib.auth.views import LoginView
from axes.models import AccessAttempt

class CustomLoginView(LoginView):
    """Custom Login View to track and display remaining Axes login attempts"""
    template_name = 'registration/login.html' # Points to your existing login page

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            username = self.request.POST.get('username')
            if username:
                attempt = AccessAttempt.objects.filter(username=username).first()
                if attempt:
                    remaining = 5 - attempt.failures_since_start
                    if remaining > 0:
                        context['axes_warning'] = f"Warning: Incorrect credentials. You have {remaining} attempts remaining before account lockout."
        return context


@login_required
def login_success_router(request):
    """Bulletproof router that auto-heals orphaned accounts"""
    user = request.user

    # 1. Admin/Staff -> Analytics Dashboard
    if user.is_superuser or user.is_staff:
        return redirect('clinic_reports')

    # 2. Doctor -> Doctor Dashboard
    if hasattr(user, 'doctor'):
        return redirect('doctor_dashboard')

    # 3. Patient -> Auto-Heal and Redirect
    # If a profile doesn't exist, this automatically builds one so they never get stuck!
    PatientProfile.objects.get_or_create(user=user)
    return redirect('patient_dashboard')

def register_patient(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            PatientProfile.objects.create(user=user)
            # FIX: Explicitly tell Django which backend to use so Axes doesn't crash!
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('patient_dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'appointments/register.html', {'form': form})


@login_required
def patient_dashboard(request):
    if hasattr(request.user, 'doctor'):
        return redirect('doctor_dashboard')
    if request.user.is_superuser or request.user.is_staff:
        return redirect('clinic_reports')

    profile, created = PatientProfile.objects.get_or_create(user=request.user)
    # FIX: Removed the '-' so it sorts ascending chronologically
    appointments = Appointment.objects.filter(patient=request.user).order_by('appointment_date', 'appointment_time')
    return render(request, 'appointments/patient_dashboard.html', {
        'profile': profile,
        'appointments': appointments
    })

@login_required
def doctor_dashboard(request):
    if not hasattr(request.user, 'doctor'):
        return redirect('patient_dashboard')

    today = date.today()
    doctor = request.user.doctor

    todays_queue = Token.objects.filter(
        appointment__doctor=doctor,
        appointment__appointment_date=today
    ).order_by('token_number')

    upcoming_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date__gt=today
    ).order_by('appointment_date', 'appointment_time')

    return render(request, 'appointments/doctor_dashboard.html', {
        'doctor': doctor,
        'queue': todays_queue,
        'upcoming': upcoming_appointments,
        'today': today
    })
from django.core.exceptions import ObjectDoesNotExist


@login_required
def cancel_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    is_patient = (appointment.patient == request.user)
    is_doctor = False

    try:
        if request.user.doctor == appointment.doctor:
            is_doctor = True
    except ObjectDoesNotExist:
        pass

    if is_patient or is_doctor:
        appointment.status = 'Cancelled'
        appointment.save()

        # FIX: Let the Smart Sorter safely delete the token and shift the line!
        recalculate_queue(appointment.doctor, appointment.appointment_date)

        messages.success(request, "Appointment successfully cancelled.")
    else:
        messages.error(request, "Security Exception: You do not have permission to modify this record.")

    try:
        if hasattr(request.user, 'doctor'):
            return redirect('doctor_dashboard')
    except ObjectDoesNotExist:
        pass

    return redirect('patient_dashboard')


@login_required
def reschedule_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    is_patient = appointment.patient == request.user
    is_doctor = hasattr(request.user, 'doctor') and appointment.doctor == request.user.doctor
    if not (is_patient or is_doctor):
        return redirect('patient_dashboard')

    if request.method == 'POST':
        new_date_str = request.POST.get('appointment_date')
        new_time = request.POST.get('appointment_time')
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()

        if Appointment.objects.filter(doctor=appointment.doctor, appointment_date=new_date, appointment_time=new_time, status='Scheduled').exclude(id=appointment.id).exists():
            return render(request, 'appointments/reschedule.html', {
                'appointment': appointment, 'time_slots': TIME_SLOTS,
                'error': 'That time slot is already taken.'
            })

        old_date = appointment.appointment_date
        old_doctor = appointment.doctor

        appointment.appointment_date = new_date
        appointment.appointment_time = new_time
        appointment.save()

        # Resort the queue for the day they left
        if old_date != new_date:
            recalculate_queue(old_doctor, old_date)

        # Resort the queue for their new day
        recalculate_queue(appointment.doctor, new_date)

        # Grab their new dynamic token
        new_token = appointment.token.token_number

        send_mock_notification(appointment.patient, "BOOKING_CONFIRMED", {
            'doctor': appointment.doctor.name, 'date': new_date, 'time': new_time, 'token': new_token
        })

        return redirect('doctor_dashboard' if is_doctor else 'patient_dashboard')

    return render(request, 'appointments/reschedule.html', {'appointment': appointment, 'time_slots': TIME_SLOTS})


@login_required
def book_appointment(request):
    doctors = Doctor.objects.all()

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor_id')
        date_str = request.POST.get('appointment_date')
        time_slot = request.POST.get('appointment_time')

        if not time_slot:
            return render(request, 'appointments/book.html', {
                'doctors': doctors, 'time_slots': TIME_SLOTS,
                'error': 'System error: Time slot was missing.'
            })

        doctor = Doctor.objects.get(id=doctor_id)
        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        if Appointment.objects.filter(doctor=doctor, appointment_date=appt_date, appointment_time=time_slot, status='Scheduled').exists():
            return render(request, 'appointments/book.html', {
                'doctors': doctors, 'time_slots': TIME_SLOTS,
                'error': 'This time slot is already booked. Please select another time.'
            })

        appointment = Appointment.objects.create(
            patient=request.user, doctor=doctor,
            appointment_date=appt_date, appointment_time=time_slot
        )

        # Trigger the Smart Sorter instead of guessing the token
        recalculate_queue(doctor, appt_date)

        # Grab the freshly generated token
        new_token_num = appointment.token.token_number

        send_mock_notification(request.user, "BOOKING_CONFIRMED", {
            'doctor': doctor.name, 'date': appt_date, 'time': time_slot, 'token': new_token_num
        })

        return render(request, 'appointments/success.html', {'token_number': new_token_num})

    return render(request, 'appointments/book.html', {'doctors': doctors, 'time_slots': TIME_SLOTS})


@login_required
def clinic_reports(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')

    today = date.today()
    todays_total = Appointment.objects.filter(appointment_date=today).count()
    todays_completed = Appointment.objects.filter(appointment_date=today, status='Completed').count()

    doctor_stats = Doctor.objects.annotate(
        total_appointments=Count('appointment'),
        today_appointments=Count('appointment', filter=Q(appointment__appointment_date=today))
    )

    master_queue = Token.objects.filter(
        appointment__appointment_date=today
    ).select_related('appointment', 'appointment__doctor', 'appointment__patient').order_by('appointment__doctor__name', 'token_number')

    return render(request, 'appointments/reports.html', {
        'today': today,
        'todays_total': todays_total,
        'todays_completed': todays_completed,
        'doctor_stats': doctor_stats,
        'master_queue': master_queue
    })

def api_current_token(request, doctor_id):
    today = date.today()
    last_served_token = Token.objects.filter(
        appointment__doctor_id=doctor_id,
        appointment__appointment_date=today,
        is_served=True
    ).aggregate(Max('token_number'))['token_number__max']

    return JsonResponse({'status': 'success', 'current_token': last_served_token or 0})

@login_required
def edit_profile(request):
    profile, created = PatientProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            return redirect('patient_dashboard')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)

    return render(request, 'appointments/edit_profile.html', {'u_form': u_form, 'p_form': p_form})

@login_required
def mark_served(request, token_id):
    if hasattr(request.user, 'doctor'):
        token = get_object_or_404(Token, id=token_id, appointment__doctor=request.user.doctor)
        token.is_served = True
        token.save()

        token.appointment.status = 'Completed'
        token.appointment.save()

    return redirect('doctor_dashboard')

@login_required
def download_report(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Clinic_Report_{date.today()}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Time', 'Patient Name', 'Doctor', 'Token Number', 'Status'])

    appointments = Appointment.objects.all().order_by('-appointment_date', 'appointment_time')

    for appt in appointments:
        token_num = appt.token.token_number if hasattr(appt, 'token') else "N/A"
        writer.writerow([
            appt.appointment_date,
            appt.appointment_time,
            appt.patient.username.title(),
            f"Dr. {appt.doctor.name}",
            token_num,
            appt.status
        ])

    return response

@login_required
def all_time_logs(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')

    logs = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')
    return render(request, 'appointments/all_logs.html', {'logs': logs})

@login_required
def export_lifetime_logs(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="ClinicCare_Lifetime_Logs.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Time', 'Patient Name', 'Doctor', 'Status'])

    logs = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')

    for log in logs:
        writer.writerow([
            log.appointment_date,
            log.appointment_time,
            log.patient.username,
            log.doctor.name,
            log.status
        ])

    return response