from django.contrib import admin
from django.urls import path, include
from appointments.views import CustomLoginView

urlpatterns = [
    path('clinic-hq-vault-88/', admin.site.urls),
    # FIX: Intercept the login URL to use our new Tracker View
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('appointments.urls')),
]