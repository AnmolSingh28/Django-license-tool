from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import License, AdminSettings
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from .serializers import (
    LicenseSerializer, 
    LicenseValidationSerializer,
    LicenseRenewalSerializer
)
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.views.decorators.http import require_GET
from django.contrib.auth.views import LogoutView
import brevo_python
from brevo_python.rest import ApiException
from pprint import pprint
from django.conf import settings

configuration = brevo_python.Configuration()
configuration.api_key['api-key'] = settings.BREVO_API_KEY
def user_login(request):
    return redirect('login')

def register(request):
    if request.method=='POST':
        form=UserCreationForm(request.POST)
        if form.is_valid():
            user=form.save(commit=False)
            if not User.objects.exists():
                user.is_staff=True
                user.is_superuser=True
                messages.success(request,'Welcome! You have been granted admin rights. Please log in to the admin panel for settings and more.')
            else:
                messages.success(request,'Registration successful! You can now log in.')
            user.save()
            login(request,user)
            return redirect('home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request,f"Error in {field}:{error}")
    else:
        form=UserCreationForm()
    return render(request,'registration/register.html',{'form': form})

def home(request):
    has_license=License.objects.filter(user=request.user).exists() 
    context={'has_license':has_license}
    return render(request,'licenses/home.html',context)

@require_GET
def custom_logout(request):
    return LogoutView.as_view()(request)

@login_required
def license_list(request):
    is_admin=request.user.is_superuser
    licenses=list(License.objects.all().order_by('-created_at')) if is_admin \
               else list(License.objects.filter(user=request.user).order_by('-created_at'))

    if request.method=='POST':
        license_id=request.POST.get('license_id')
        target_license=next((lic for lic in licenses if str(lic.id)==license_id), None)

        if not target_license:
            messages.error(request,"License not found.")
        elif target_license.user != request.user and not is_admin:
            messages.error(request,"You do not have permission for this action")
        else:
            if 'view_license_key' in request.POST:
                raw_password = request.POST.get('view_password')
                if target_license.decrypt_actual_key(raw_password):
                    messages.success(request, f"Key revealed for'{target_license.user.username}'!")
                else:
                    messages.error(request, "Incorrect password or decryption failed")
            elif 'set_license_password' in request.POST:
                new_pass=request.POST.get('new_view_password')
                confirm_pass=request.POST.get('confirm_view_password')
                raw_key_for_re_enc=request.POST.get('raw_license_key_for_re_encryption')

                if not new_pass or not confirm_pass:
                    messages.error(request,"New password and confirmation are required")
                elif new_pass!= confirm_pass:
                    messages.error(request,"New passwords do not match")
                elif not raw_key_for_re_enc:
                    messages.error(request,"Original raw license key is required for password setup")
                else:
                    try:
                        target_license.set_license_view_password_and_encrypt_key(new_pass, raw_key_for_re_enc)
                        target_license.save()
                        messages.success(request, "License view password set successfully!")
                    except Exception as e:
                        messages.error(request, f"Error setting password: {e}")
    
    view_title="All Licenses (Admin View)" if is_admin else "Your Licenses"
    context={
        'licenses':licenses,
        'view_title':view_title,
        'is_admin':is_admin,
    }
    return render(request,'licenses/list.html',context)

@staff_member_required
def create_license(request):
    if request.method=='POST':
        user_id=request.POST.get('user_id')
        days=int(request.POST.get('days', 365))
        initial_view_password=request.POST.get('initial_view_password')
        if not user_id or not initial_view_password:
            messages.error(request,'User and Initial View Password are required.')
            return redirect('create-license')
        try:
            user=get_object_or_404(User,id=user_id)
            generated_raw_key=License.generate_random_raw_key()
            license= License(
                user=user,
                expires_at=timezone.now()+timedelta(days=days),
                status='active'
            )
            license.set_license_view_password_and_encrypt_key(initial_view_password, generated_raw_key)
            license.save()
            if 'create_another' in request.POST:
                messages.success(request,f'License created for {user.email}')
                return redirect('create-license')
            else:
                messages.success(request, f'License {license.displayed_key[:12]}... created successfully for {user.email}!')
                return redirect('license-list')
                
        except Exception as e:
            messages.error(request,f'Error creating license:{str(e)}')
            return redirect('create-license')
    users = User.objects.all().order_by('username')
    return render(request,'licenses/create.html', {
        'users':users,
        'preselected_user':request.GET.get('user_id')
    })

def verify_license(request):
    if request.method=='POST':
        license_key=request.POST.get('license_key')
        try:
            license=License.objects.get(key=license_key)
            return render(request,'licenses/verify_result.html', {
                'license':license,
                'is_valid':license.is_valid
            })
        except License.DoesNotExist:
            messages.error(request,"Invalid license key")
    
    return render(request,'licenses/verify.html')

@login_required
def renew_license(request, pk):
    license=get_object_or_404(License, pk=pk)
    if request.method=='POST':
        try:
            days=int(request.POST.get('days',30)) 
            license.renew(days)
            messages.success(request,f'License renewed! New expiry:{license.expires_at.date()}')
            return redirect('license-list')
        except ValueError:
            messages.error(request,'Invalid number of days')
    
    default_days=30
    if license.expires_at<timezone.now():
        default_days=90 
    
    return render(request,'licenses/renew.html',{
        'license':license,
        'default_days':default_days
    })
def license_request(request):
    if request.method == 'POST':
        requester_email = request.POST.get('requester_email', '')
        requirements = request.POST.get('requirements', '')

        if not requester_email or not requirements:
            messages.error(request, "Email and requirements are required to send the license request.")
            return redirect('home')
        admin_settings = AdminSettings.objects.first()
        if not admin_settings or not admin_settings.license_request_email:
            messages.error(request, "Admin email not configured. Please contact support.")
            return redirect('home')
        api_instance = brevo_python.TransactionalEmailsApi(brevo_python.ApiClient(configuration))

        sender = {"name":"License System","email": settings.DEFAULT_FROM_EMAIL}
        to = [{"email": admin_settings.license_request_email,"name": "Admin"}]

        html_content = f"""
        <html>
        <body>
            <h1>New License Request</h1>
            <p><strong>Requester Email:</strong> {requester_email}</p>
            <p><strong>Requirements:</strong> {requirements}</p>
            <p>Plz log in to the admin panel to process this request.</p>
        </body>
        </html>
        """
        subject = "New License Request Received!"
        send_smtp_email = brevo_python.SendSmtpEmail(
            to=to,
            html_content=html_content,
            sender=sender,
            subject=subject
        )
        try:
            api_response = api_instance.send_transac_email(send_smtp_email)
            pprint(api_response)
            messages.success(request,"Your license request has been sent successfully! We'll get back to you soon")
            return redirect('home')
        except ApiException as e:
            print(f"Exception when calling TransactionalEmailsApi->send_transac_email: {e}\n")
            messages.error(request,"Failed to send license request email. Please try again or contact support")
            return redirect('home')
        except Exception as e:
            print(f"An unexpected error occurred: {e}\n")
            messages.error(request,"An unexpected error occurred while sending the email. Please try again")
            return redirect('home')
    return redirect('home')


class LicenseAPI(APIView):
    permission_classes=[IsAdminUser]

    def get(self,request):
        licenses=License.objects.all()
        serializer=LicenseSerializer(licenses,many=True)
        return Response(serializer.data)

    def post(self,request):
        serializer=LicenseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_201_CREATED)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

class ValidateLicenseAPI(APIView):
    def post(self,request):
        serializer=LicenseValidationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                license=License.objects.get(key=serializer.validated_data['license_key'])
                if license.hardware_id and license.hardware_id != serializer.validated_data.get('hardware_id'):
                    return Response({'valid':False,'error':'Hardware ID mismatch'})
                
                return Response({
                    'valid':license.is_valid,
                    'expires_at':license.expires_at,
                    'status':license.status
                })
            except License.DoesNotExist:
                return Response({'valid':False,'error':'Invalid license'})
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

@login_required
class RenewLicenseAPI(APIView):
    permission_classes=[IsAuthenticated]

    def post(self,request):
        serializer=LicenseRenewalSerializer(data=request.data)
        if serializer.is_valid():
            try:
                license=License.objects.get(
                    key=serializer.validated_data['license_key'],
                    user=request.user
                )
                license.renew(days=serializer.validated_data['days'])
                return Response({'success':True,'new_expiry':license.expires_at})
            except License.DoesNotExist:
                return Response({'error':'License not found'},status=404)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

class LicenseDetailAPI(APIView):
    permission_classes=[IsAdminUser]    

    def get(self,request,pk):
        license=get_object_or_404(License,pk=pk)
        serializer=LicenseSerializer(license)
        return Response(serializer.data)

    def patch(self,request,pk):
        license=get_object_or_404(License,pk=pk)
        serializer=LicenseSerializer(license,data=request.data,partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        license=get_object_or_404(License,pk=pk)
        license.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)