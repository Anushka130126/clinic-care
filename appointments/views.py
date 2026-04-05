from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.db.models import Max, Count, Q
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from datetime import datetime, date

import openpyxl
from django.http import HttpResponse

from .models import Doctor, Appointment, Token, TIME_SLOTS, PatientProfile
from .utils import send_mock_notification,recalculate_queue
from .forms import UserUpdateForm, ProfileUpdateForm

from django.contrib.auth.views import LoginView
from axes.models import AccessAttempt

from .forms import PatientRegistrationForm, UserUpdateForm, ProfileUpdateForm # Added PatientRegistrationForm
from django.contrib.auth.models import User

from .models import DiagnosisReport
from .forms import DiagnosisForm

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
        # FIX: Use the new custom form
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # No need to manually create the profile here anymore, the form handles it safely!
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('patient_dashboard')
    else:
        form = PatientRegistrationForm()
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
    is_doctor = hasattr(request.user, 'doctor') and appointment.doctor == request.user.doctor

    if is_patient or is_doctor:
        appointment.status = 'Cancelled'
        appointment.save()

        # Safely delete the token to wipe it from the queue
        if hasattr(appointment, 'token'):
            appointment.token.delete()

        # Trigger the newly fixed Smart Sorter
        recalculate_queue(appointment.doctor, appointment.appointment_date)

        messages.success(request, "Appointment successfully cancelled.")
    else:
        messages.error(request, "Security Exception: Unauthorized.")

    if hasattr(request.user, 'doctor'):
        return redirect('doctor_dashboard')
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

        # --- NEW: TIME TRAVEL PREVENTION ---
        current_date = datetime.now().date()
        current_time = datetime.now().time()

        try:
            new_time_obj = datetime.strptime(new_time, '%H:%M').time()
        except ValueError:
            new_time_obj = datetime.strptime(new_time, '%I:%M %p').time()

        if new_date < current_date:
            return render(request, 'appointments/reschedule.html', {
                'appointment': appointment, 'time_slots': TIME_SLOTS,
                'error': 'Invalid Request: You cannot reschedule to a past date.'
            })

        if new_date == current_date and new_time_obj < current_time:
            return render(request, 'appointments/reschedule.html', {
                'appointment': appointment, 'time_slots': TIME_SLOTS,
                'error': 'Invalid Request: That time slot has already passed today.'
            })
        # -----------------------------------

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

        if old_date != new_date:
            recalculate_queue(old_doctor, old_date)
        recalculate_queue(appointment.doctor, new_date)
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

        # --- NEW: TIME TRAVEL PREVENTION ---
        current_date = datetime.now().date()
        current_time = datetime.now().time()

        # Safely convert the string time slot into a readable Python time object
        try:
            appt_time_obj = datetime.strptime(time_slot, '%H:%M').time()
        except ValueError:
            appt_time_obj = datetime.strptime(time_slot, '%I:%M %p').time()

        if appt_date < current_date:
            return render(request, 'appointments/book.html', {
                'doctors': doctors, 'time_slots': TIME_SLOTS,
                'error': 'Invalid Request: You cannot book an appointment in the past.'
            })

        if appt_date == current_date and appt_time_obj < current_time:
            return render(request, 'appointments/book.html', {
                'doctors': doctors, 'time_slots': TIME_SLOTS,
                'error': 'Invalid Request: That time slot has already passed today.'
            })
        # -----------------------------------

        if Appointment.objects.filter(doctor=doctor, appointment_date=appt_date, appointment_time=time_slot, status='Scheduled').exists():
            return render(request, 'appointments/book.html', {
                'doctors': doctors, 'time_slots': TIME_SLOTS,
                'error': 'This time slot is already booked. Please select another time.'
            })

        appointment = Appointment.objects.create(
            patient=request.user, doctor=doctor,
            appointment_date=appt_date, appointment_time=time_slot
        )

        recalculate_queue(doctor, appt_date)
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
    """Allows patient to securely update their medical history"""

    # Security: Kick out doctors and admins
    if hasattr(request.user, 'doctor') or request.user.is_staff:
        return redirect('patient_dashboard')

    profile, created = PatientProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # Now we only have to process ONE form!
        form = ProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Medical history successfully updated!")
            return redirect('patient_dashboard')
    else:
        form = ProfileUpdateForm(instance=profile)

    return render(request, 'appointments/edit_profile.html', {'form': form})

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
    """Generates a real .xlsx Excel report for the daily clinic stats"""
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Clinic_Report_{date.today()}.xlsx"'

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Daily Report'
    sheet.append(['Date', 'Time', 'Patient Name', 'Doctor', 'Token Number', 'Status'])

    appointments = Appointment.objects.all().order_by('-appointment_date', 'appointment_time')
    for appt in appointments:
        token_num = appt.token.token_number if hasattr(appt, 'token') else "N/A"
        sheet.append([
            str(appt.appointment_date), str(appt.appointment_time),
            appt.patient.username.title(), f"Dr. {appt.doctor.name}",
            token_num, appt.status
        ])

    workbook.save(response)
    return response

@login_required
def export_lifetime_logs(request):
    """Generates a real .xlsx Excel report of all lifetime appointments"""
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="ClinicCare_Lifetime_Logs.xlsx"'

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Lifetime Logs'
    sheet.append(['Date', 'Time', 'Patient Name', 'Doctor', 'Status'])

    logs = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')
    for log in logs:
        sheet.append([
            str(log.appointment_date), str(log.appointment_time),
            log.patient.username.title(), f"Dr. {log.doctor.name}", log.status
        ])

    workbook.save(response)
    return response

@login_required
def all_time_logs(request):
    """Displays the lifetime history of all appointments for Admins"""
    # Security Check: Only Admins allowed
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')

    # Fetch every appointment ever made, sorted by newest first
    logs = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')

    return render(request, 'appointments/all_logs.html', {'logs': logs})



@login_required
def purge_legacy_data(request):
    """Temporary Kill Switch to wipe bad data without Render Shell"""

    # Ultimate Security Check: Only you (the Admin) can do this
    if not request.user.is_superuser:
        return HttpResponse("<h1>Security Violation: Unauthorized</h1>", status=403)

    # 1. Vaporize all appointments and queue tokens
    Appointment.objects.all().delete()
    Token.objects.all().delete()

    # 2. Vaporize all test patients (but strictly ignore Admins and Doctors)
    User.objects.filter(is_superuser=False, is_staff=False, doctor__isnull=True).delete()
    PatientProfile.objects.all().delete()

    return HttpResponse("""
        <div style="font-family: sans-serif; text-align: center; margin-top: 50px;">
            <h1 style="color: green;">Wipe successful!</h1>
            <p>Legacy patients, appointments, and tokens have been destroyed.</p>
            <p>Your Doctors and Admins are completely safe.</p>
            <a href="/dashboard/">Go back to Dashboard</a>
        </div>
    """)



@login_required
def write_diagnosis(request, appt_id):
    """Doctor creates or edits a diagnosis report"""
    appointment = get_object_or_404(Appointment, id=appt_id)

    # Security: Only the assigned doctor can write the report
    if not hasattr(request.user, 'doctor') or appointment.doctor != request.user.doctor:
        messages.error(request, "Unauthorized access.")
        return redirect('doctor_dashboard')

    # Fetch existing report if editing, or create a new one
    try:
        report = appointment.diagnosis
    except ObjectDoesNotExist:
        report = None

    if request.method == 'POST':
        form = DiagnosisForm(request.POST, instance=report)
        if form.is_valid():
            new_report = form.save(commit=False)
            new_report.appointment = appointment
            new_report.save()

            # Automatically mark the appointment as completed!
            appointment.status = 'Completed'
            appointment.save()

            messages.success(request, "Diagnosis Report saved successfully!")
            return redirect('doctor_dashboard')
    else:
        form = DiagnosisForm(instance=report)

    return render(request, 'appointments/write_diagnosis.html', {'form': form, 'appointment': appointment})

@login_required
def view_diagnosis(request, appt_id):
    """Patient or Doctor views the final report card"""
    appointment = get_object_or_404(Appointment, id=appt_id)

    # Security: Only the specific patient or doctor can read it
    is_patient = appointment.patient == request.user
    is_doctor = hasattr(request.user, 'doctor') and appointment.doctor == request.user.doctor

    if not (is_patient or is_doctor):
        return redirect('patient_dashboard')

    try:
        report = appointment.diagnosis
    except ObjectDoesNotExist:
        messages.warning(request, "The doctor has not written a report for this appointment yet.")
        return redirect('patient_dashboard' if is_patient else 'doctor_dashboard')

    return render(request, 'appointments/view_diagnosis.html', {'report': report, 'appointment': appointment})