
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  # <--- THIS IS THE CRITICAL LINE
    path('', include('appointments.urls')), # (Your custom app routes)
]