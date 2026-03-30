from django.urls import path
from . import views
from django.urls import reverse_lazy
from django.views.generic import RedirectView

urlpatterns = [
    urlpatterns = [
    path('', RedirectView.as_view(url=reverse_lazy('login')), name='home'),
    
    # Dashboards
    path('dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('doctor-dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('reports/', views.clinic_reports, name='clinic_reports'),
    path('reports/logs/', views.all_time_logs, name='all_time_logs'),
    path('reports/download/', views.download_report, name='download_report'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Booking Flow
    path('book/', views.book_appointment, name='book_appointment'),
    path('reschedule/<int:appointment_id>/', views.reschedule_appointment, name='reschedule_appointment'),
    path('cancel/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),
    
    # API & Auth
    path('api/queue/<int:doctor_id>/', views.api_current_token, name='api_queue'),
    path('register/', views.register_patient, name='register'),

    path('token/<int:token_id>/serve/', views.mark_served, name='mark_served'),

]