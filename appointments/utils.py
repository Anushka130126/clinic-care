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