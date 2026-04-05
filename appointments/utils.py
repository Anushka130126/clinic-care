def send_mock_notification(user, notification_type, context):
    """
    University Requirement: Mock SMS/Email System.
    Intercepts the booking and prints a live receipt to the server terminal.
    """
    print("\n" + "="*55)
    print(" 🔔 CLINIC-CARE MOCK SMS/EMAIL DISPATCH SYSTEM 🔔")
    print("="*55)
    print(f"TO PATIENT: {user.username.title()}")
    
    # Safely grab the contact info
    email = user.email if user.email else "No email provided"
    phone = "No phone provided"
    
    if hasattr(user, 'patientprofile') and user.patientprofile.phone_number:
        phone = user.patientprofile.phone_number
        
    print(f"ROUTING: [Email: {email}] | [SMS: {phone}]")
    print("-" * 55)
    
    # Format the message based on the action
    if notification_type == "BOOKING_CONFIRMED":
        print(f"MESSAGE: Hello {user.username.title()}, your appointment")
        print(f"with Dr. {context.get('doctor')} is officially confirmed.")
        print(f"DATE & TIME: {context.get('date')} at {context.get('time')}")
        print(f"YOUR LIVE QUEUE TOKEN IS: #{context.get('token')}")
        print("Please arrive 10 minutes early to check in.")
        
    print("="*55 + "\n")
    return True

def recalculate_queue(doctor, target_date):
    """
    Mathematically perfect queue logic:
    1. Destroys tokens belonging to Cancelled appointments.
    2. Sorts all remaining Scheduled/Completed appointments strictly by Time.
    3. Assigns them perfectly contiguous queue numbers (1, 2, 3...).
    """
    from .models import Appointment, Token # Imported here to avoid circular logic
    from django.core.exceptions import ObjectDoesNotExist

    # 1. Strip tokens from anyone who cancelled
    Token.objects.filter(
        appointment__doctor=doctor,
        appointment__appointment_date=target_date,
        appointment__status='Cancelled'
    ).delete()

    # 2. Fetch all remaining active appointments, perfectly sorted by Time
    active_appts = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=target_date
    ).exclude(status='Cancelled').order_by('appointment_time')

    # 3. Linearly assign contiguous queue numbers
    counter = 1
    for appt in active_appts:
        try:
            # If they already have a token, update its number if the queue shifted
            token = Token.objects.get(appointment=appt)
            if token.token_number != counter:
                token.token_number = counter
                token.save()
        except ObjectDoesNotExist:
            # If they are brand new, generate their token
            Token.objects.create(appointment=appt, token_number=counter)
        counter += 1


