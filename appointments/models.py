from django.db import models
from django.contrib.auth.models import User
from datetime import date

TIME_SLOTS = [
    ('09:00', '09:00 AM'), ('09:30', '09:30 AM'), ('10:00', '10:00 AM'),
    ('10:30', '10:30 AM'), ('11:00', '11:00 AM'), ('11:30', '11:30 AM'),
    ('12:00', '12:00 PM'), ('12:30', '12:30 PM'), ('14:00', '02:00 PM'),
]

class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True)
    medical_history = models.TextField(blank=True, default="No prior history recorded.")
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    specialization = models.CharField(max_length=50)
    
    def __str__(self):
        return f"Dr. {self.name} ({self.specialization})"

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('Scheduled', 'Scheduled'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled')
    ]
    
    patient = models.ForeignKey(User, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    appointment_date = models.DateField(default=date.today)
    appointment_time = models.CharField(max_length=10, choices=TIME_SLOTS, default='09:00')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')

    class Meta:
        unique_together = ('doctor', 'appointment_date', 'appointment_time', 'status')

class Token(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE)
    token_number = models.IntegerField()
    is_served = models.BooleanField(default=False)