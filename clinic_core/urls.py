
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('clinic-hq-vault-88/', admin.site.urls),
    path('', include('appointments.urls')), 
]