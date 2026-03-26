from django.contrib import admin
from .models import Doctor, Appointment, Token

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialization')
    search_fields = ('name', 'specialization')

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'appointment_date', 'status')
    list_filter = ('appointment_date', 'doctor', 'status')
    search_fields = ('patient__username',)
    date_hierarchy = 'appointment_date'

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('token_number', 'get_doctor', 'get_date', 'is_served')
    list_filter = ('is_served', 'appointment__appointment_date')
    
    def get_doctor(self, obj):
        return obj.appointment.doctor.name
    get_doctor.short_description = 'Doctor'
    
    def get_date(self, obj):
        return obj.appointment.appointment_date
    get_date.short_description = 'Date'
