from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Max, Count, Q
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from .models import Doctor, Appointment, Token, TIME_SLOTS, PatientProfile
from .utils import send_mock_notification
from datetime import datetime, date
from .forms import UserUpdateForm, ProfileUpdateForm
import csv
from django.http import HttpResponse
from django.http import HttpResponseRedirect

def register_patient(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create a blank profile to hold phone numbers/medical history later
            PatientProfile.objects.create(user=user)
            login(request, user)
            return redirect('patient_dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'appointments/register.html', {'form': form})

@login_required
def patient_dashboard(request):
    # --- SMART ROUTING INTERCEPTOR ---
    # If a Doctor logs in, instantly route them to the Doctor Workspace
    if hasattr(request.user, 'doctor'):
        return redirect('doctor_dashboard')
    # If an Admin logs in, instantly route them to the Analytics Reports
    if request.user.is_superuser or request.user.is_staff:
        return redirect('clinic_reports')

    # --- NORMAL PATIENT LOGIC ---
    """Patient Profile & Upcoming Appointments"""
    profile, created = PatientProfile.objects.get_or_create(user=request.user)
    appointments = Appointment.objects.filter(patient=request.user).order_by('-appointment_date')
    return render(request, 'appointments/patient_dashboard.html', {
        'profile': profile, 
        'appointments': appointments
    })

@login_required
def doctor_dashboard(request):
    """Doctor's specific queue and schedule viewer"""
    if not hasattr(request.user, 'doctor'):
        return redirect('patient_dashboard') # Security check
        
    today = date.today()
    doctor = request.user.doctor
    
    # Fetch today's live queue
    todays_queue = Token.objects.filter(
        appointment__doctor=doctor, 
        appointment__appointment_date=today
    ).order_by('token_number')
    
    # --- NEW: Fetch upcoming future appointments ---
    upcoming_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date__gt=today
    ).order_by('appointment_date', 'appointment_time')
    
    return render(request, 'appointments/doctor_dashboard.html', {
        'doctor': doctor,
        'queue': todays_queue,
        'upcoming': upcoming_appointments, # Pass the new data to the HTML
        'today': today
    })


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

@login_required
def cancel_appointment(request, pk):
    """Allows either the Patient or the Doctor to cancel the appointment"""
    # Grab the appointment (without filtering by user yet)
    appointment = get_object_or_404(Appointment, pk=pk)
    
    # Check roles: Is the user the patient who booked it, OR the assigned doctor?
    is_patient = hasattr(request.user, 'patient') and appointment.patient == request.user.patient
    is_doctor = hasattr(request.user, 'doctor') and appointment.doctor == request.user.doctor
    
    if is_patient or is_doctor:
        appointment.status = 'Cancelled'
        appointment.save()
        
        # If the appointment has a live queue token, mark it as served so it leaves the queue
        if hasattr(appointment, 'token'):
            appointment.token.is_served = True
            appointment.token.save()
            
        messages.success(request, "Appointment successfully cancelled.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
    else:
        # Security trigger if a random user tries to cancel someone else's booking
        messages.error(request, "Security Exception: You do not have permission to modify this record.")
        

@login_required
def reschedule_appointment(request, appointment_id):
    """Handles logic for changing an appointment time safely"""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Security: Only the owning patient or the assigned doctor can reschedule
    is_patient = appointment.patient == request.user
    is_doctor = hasattr(request.user, 'doctor') and appointment.doctor == request.user.doctor
    if not (is_patient or is_doctor):
        return redirect('patient_dashboard')

    if request.method == 'POST':
        new_date_str = request.POST.get('appointment_date')
        new_time = request.POST.get('appointment_time')
        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        
        # Collision Check
        if Appointment.objects.filter(doctor=appointment.doctor, appointment_date=new_date, appointment_time=new_time, status='Scheduled').exclude(id=appointment.id).exists():
            return render(request, 'appointments/reschedule.html', {
                'appointment': appointment, 'time_slots': TIME_SLOTS,
                'error': 'That time slot is already taken.'
            })
            
        appointment.appointment_date = new_date
        appointment.appointment_time = new_time
        appointment.save()
        
        # Trigger Mock Notification
        send_mock_notification(appointment.patient, "BOOKING_CONFIRMED", {
            'doctor': appointment.doctor.name, 'date': new_date, 'time': new_time, 'token': appointment.token.token_number
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
        
        # Collision Check Logic (Ignores cancelled appointments)
        if Appointment.objects.filter(doctor=doctor, appointment_date=appt_date, appointment_time=time_slot, status='Scheduled').exists():
            return render(request, 'appointments/book.html', {
                'doctors': doctors, 'time_slots': TIME_SLOTS,
                'error': 'This time slot is already booked. Please select another time.'
            })
            
        # Create Appointment
        appointment = Appointment.objects.create(
            patient=request.user, doctor=doctor,
            appointment_date=appt_date, appointment_time=time_slot
        )
        
        # Dynamic Token Logic
        last_token = Token.objects.filter(
            appointment__doctor=doctor, 
            appointment__appointment_date=appt_date
        ).aggregate(Max('token_number'))['token_number__max']
        
        new_token_num = (last_token or 0) + 1
        
        Token.objects.create(appointment=appointment, token_number=new_token_num)
        
        # Trigger Mock Notification
        send_mock_notification(request.user, "BOOKING_CONFIRMED", {
            'doctor': doctor.name, 'date': appt_date, 'time': time_slot, 'token': new_token_num
        })
        
        return render(request, 'appointments/success.html', {'token_number': new_token_num})
        
    return render(request, 'appointments/book.html', {'doctors': doctors, 'time_slots': TIME_SLOTS})

@login_required
def clinic_reports(request):
    """Generates Daily and Doctor-wise analytics with Master Queue"""
    # Security: Ensure only staff/doctors can view reports
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')
        
    today = date.today()
    
    todays_total = Appointment.objects.filter(appointment_date=today).count()
    todays_completed = Appointment.objects.filter(appointment_date=today, status='Completed').count()
    
    doctor_stats = Doctor.objects.annotate(
        total_appointments=Count('appointment'),
        today_appointments=Count('appointment', filter=Q(appointment__appointment_date=today))
    )
    
    # --- Fetch the Master Queue for all doctors today ---
    master_queue = Token.objects.filter(
        appointment__appointment_date=today
    ).select_related('appointment', 'appointment__doctor', 'appointment__patient').order_by('appointment__doctor__name', 'token_number')
    
    return render(request, 'appointments/reports.html', {
        'today': today,
        'todays_total': todays_total,
        'todays_completed': todays_completed,
        'doctor_stats': doctor_stats,
        'master_queue': master_queue # Send the queue data to the HTML
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
    """Doctor clicks this to advance the queue and complete the appointment"""
    if hasattr(request.user, 'doctor'):
        token = get_object_or_404(Token, id=token_id, appointment__doctor=request.user.doctor)
        token.is_served = True
        token.save()
        
        token.appointment.status = 'Completed'
        token.appointment.save()
        
    return redirect('doctor_dashboard')

@login_required
def download_report(request):
    """Generates a downloadable CSV Excel report for the clinic"""
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')
        
    # Create the HTTP response with a CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Clinic_Report_{date.today()}.csv"'
    
    writer = csv.writer(response)
    # Write the column headers
    writer.writerow(['Date', 'Time', 'Patient Name', 'Doctor', 'Token Number', 'Status'])
    
    # Fetch all appointments in the database
    appointments = Appointment.objects.all().order_by('-appointment_date', 'appointment_time')
    
    # Write the data rows
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
    """Displays the lifetime history of all appointments for Admins"""
    # Security Check: Only Admins allowed
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')
        
    # Fetch every appointment ever made, sorted by newest first
    logs = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')
    
    return render(request, 'appointments/all_logs.html', {'logs': logs})


@login_required
def export_lifetime_logs(request):
    """Generates a CSV of every appointment in the system"""
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('patient_dashboard')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="ClinicCare_Lifetime_Logs.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Time', 'Patient Name', 'Doctor', 'Status'])
    
    # Fetch all logs, newest first
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