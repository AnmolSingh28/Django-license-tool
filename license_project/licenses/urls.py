from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.views.generic import RedirectView
from django.contrib.auth.views import LoginView, LogoutView

urlpatterns = [
    path('',RedirectView.as_view(url='/login/')),
     path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/',LogoutView.as_view(next_page='login'),name='logout'),
    path('register/',views.register,name='register'),
    path('home/',views.home,name='home'),
    path('licenses/',views.license_list,name='license-list'),
    path('license-request/', views.license_request, name='license-request'),
    path('create/',views.create_license,name='create-license'),
    path('verify/',views.verify_license,name='verify-license'),
    path('renew/<int:pk>/',views.renew_license,name='renew-license'),
    path('request-license/',views.license_request,name='license-request'),
    path('api/licenses/',views.LicenseAPI.as_view(),name='api-licenses'),
    path('api/licenses/<int:pk>/',views.LicenseDetailAPI.as_view(),name='api-license-detail'),
    path('api/validate/',views.ValidateLicenseAPI.as_view(),name='api-validate'),
]

