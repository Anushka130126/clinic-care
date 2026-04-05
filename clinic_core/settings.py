"""
Django settings for clinic_core project.
"""
import os
from pathlib import Path
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# (We use a dummy key for local testing, but Render can inject a real one later)
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dummy-key-for-local-dev-only')

# SECURITY WARNING: don't run with debug turned on in production!
# This automatically turns off DEBUG when the code detects it is running on Render
DEBUG = os.environ.get('RENDER', '') == ''

# Allows Render (or any cloud provider) to host the application
ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'appointments',
    'axes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # <-- WhiteNoise injected here for cloud CSS/Static files!
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'clinic_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'clinic_core.wsgi.application'

# Database Setup
# Uses SQLite locally, but seamlessly switches to PostgreSQL when deployed to the cloud!
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # <-- Tells the cloud server exactly where to pack your UI files

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication Routing
LOGIN_REDIRECT_URL = 'patient_dashboard'
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# MOCK EMAIL CONFIGURATION
# Intercepts outgoing emails and saves them as text files in the project folder
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = BASE_DIR / "mock_emails"

# ==========================================
# SECURITY: DJANGO-AXES RATE LIMITING
# ==========================================
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AXES_FAILURE_LIMIT = 5  # Lock the user out after 5 wrong password attempts
AXES_COOLOFF_TIME = 1   # Keep them locked out for 1 hour
AXES_RESET_ON_SUCCESS = True  # Reset the counter if they log in successfully
AXES_LOCKOUT_TEMPLATE = 'appointments/lockout.html' # The page they see when banned
AXES_ONLY_USER_FAILURES = True  # Locks the specific account, NOT the whole WiFi network!
# Routing rules for successful logins and logouts
LOGIN_REDIRECT_URL = 'login_router'
LOGOUT_REDIRECT_URL = 'home'