from datetime import datetime

def send_mock_notification(user, message_type, details):
    """
    Simulates sending an Email and SMS notification.
    In a production environment, this would hook into Twilio or AWS SES.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    phone = user.patientprofile.phone_number if hasattr(user, 'patientprofile') else "No Phone"
    email = user.email or "No Email"
    
    print("\n" + "="*50)
    print(f"[{timestamp}] MOCK NOTIFICATION SYSTEM")
    print("="*50)
    
    if message_type == "BOOKING_CONFIRMED":
        print(f"EMAIL sent to {email}: Your appointment with {details['doctor']} is confirmed for {details['date']} at {details['time']}. Token: {details['token']}")
        print(f"SMS sent to {phone}: Clinic appt confirmed for {details['date']}. Your token is {details['token']}.")
        
    elif message_type == "APPOINTMENT_CANCELLED":
        print(f"EMAIL sent to {email}: Your appointment with {details['doctor']} on {details['date']} has been cancelled.")
        
    print("="*50 + "\n")