# 🏥 ClinicCare - Enterprise Clinic Management System

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![Django](https://img.shields.io/badge/Django-5.0+-green?style=flat-square&logo=django)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple?style=flat-square&logo=bootstrap)
![Status](https://img.shields.io/badge/Status-Production_Ready-success?style=flat-square)

An end-to-end, multi-tenant clinic management platform built with Django. Designed to streamline hospital operations by isolating workflows into three distinct architectural roles: Patient, Doctor, and Hospital Administration. 

## ✨ Core Features & Modules

### 👤 Patient Portal
* **Dynamic Registration:** Frictionless onboarding with expandable medical profiles.
* **Smart Booking Engine:** Prevents double-booking through backend time-slot collision detection.
* **Self-Service Actions:** Secure rescheduling and cancellation modules.

### 🩺 Doctor Workspace
* **Live Daily Queue:** Real-time dashboard showing today's active tokens and patient states.
* **Schedule Oversight:** Comprehensive view of all future bookings.
* **One-Click State Management:** Mark appointments as 'Completed' to advance the active queue.

### 📊 Administration & Analytics (God View)
* **Smart Routing Interceptor:** Automatically routes staff vs. patients to their respective secure workspaces upon login.
* **Enterprise Dashboard:** High-level metrics for daily load and lifetime doctor-wise performance.
* **Master Queue Accordion:** View exactly who is in every doctor's waiting room in real-time.
* **CSV Reporting Engine:** One-click export of hospital operations data into Excel-ready `.csv` formats.
* **Mock Notification Interceptor:** Captures automated booking/cancellation SMS and Email payloads and writes them to local `.txt` logs for audit trails without requiring paid third-party APIs.

## 🛠️ Tech Stack & Architecture
* **Backend:** Python, Django
* **Frontend:** HTML5, Bootstrap 5 (Responsive UI), Bootstrap Icons
* **Database:** SQLite (Local Development) / PostgreSQL (Production)
* **Cloud Infrastructure:** Gunicorn (WSGI Server), WhiteNoise (Static File Management)

## 🚀 Local Development Setup

1. **Clone the repository**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/clinic-system.git](https://github.com/YOUR_USERNAME/clinic-system.git)
   cd clinic-system