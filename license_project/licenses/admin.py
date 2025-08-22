from django.contrib import admin
from .models import AdminSettings

@admin.register(AdminSettings)
class AdminSettingsAdmin(admin.ModelAdmin):
    list_display = ['license_request_email']
