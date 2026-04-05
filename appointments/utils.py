import threading
from django.core.mail import send_mail
from django.conf import settings

class EmailThread(threading.Thread):
    """A background worker that sends the email without freezing the website"""
    def __init__(self, subject, body, recipient_list):
        self.subject = subject
        self.body = body
        self.recipient_list = recipient_list
        threading.Thread.__init__(self)

    def run(self):
        try:
            send_mail(
                subject=self.subject,
                message=self.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=self.recipient_list,
                fail_silently=False,
            )
            # NEW: Added flush=True to force the log to appear
            print(">> Live email successfully sent in the background!", flush=True)
        except Exception as e:
            # NEW: Added flush=True to force the log to appear
            print(f">> WARNING: Background email failed to send. Error: {e}", flush=True)

def send_mock_notification(user, action_type, details):
    """Logs the notification and triggers the background email thread"""

    if action_type == "BOOKING_CONFIRMED":
        subject = f"Booking Confirmed: Token #{details['token']}"
        body = (f"Hello {user.username},\n\n"
                f"Your appointment with Dr. {details['doctor']} is confirmed for {details['date']} at {details['time']}.\n"
                f"Your Queue Token is: #{details['token']}\n\n"
                f"Please arrive 10 minutes early.")

    elif action_type == "APPOINTMENT_CANCELLED":
        subject = "Appointment Cancelled"
        body = (f"Hello {user.username},\n\n"
                f"Your appointment with Dr. {details['doctor']} on {details['date']} at {details['time']} has been successfully cancelled.\n"
                f"We hope to see you again soon.")

    elif action_type == "APPOINTMENT_RESCHEDULED":
        subject = "Appointment Rescheduled"
        body = (f"Hello {user.username},\n\n"
                f"Your appointment with Dr. {details['doctor']} has been moved to {details['date']} at {details['time']}.\n"
                f"Your new Queue Token is: #{details['token']}")
    else:
        return

    # 1. The Instant Terminal Log
    print("\n" + "="*50)
    print(f"MOCK SMS/EMAIL TO: {user.email}")
    print(f"SUBJECT: {subject}")
    print(f"BODY:\n{body}")
    print("="*50 + "\n")

    # 2. Start the Background Email Thread
    if user.email:
        EmailThread(subject, body, [user.email]).start()

def recalculate_queue(doctor, target_date):
    """Indestructible Smart Sorter"""
    from .models import Appointment, Token

    # 1. Strip tokens from anyone who cancelled
    Token.objects.filter(
        appointment__doctor=doctor,
        appointment__appointment_date=target_date,
        appointment__status='Cancelled'
    ).delete()

    # 2. Fetch active appointments
    active_appts = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=target_date
    ).exclude(status='Cancelled').order_by('appointment_time')

    # 3. Linearly assign contiguous queue numbers safely
    counter = 1
    for appt in active_appts:
        # Using .filter().first() instead of .get() prevents 500 crashes!
        token = Token.objects.filter(appointment=appt).first()
        if token:
            if token.token_number != counter:
                token.token_number = counter
                token.save()
        else:
            Token.objects.create(appointment=appt, token_number=counter)
        counter += 1


