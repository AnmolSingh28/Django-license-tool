from rest_framework import serializers
from .models import License
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=['id','username','email']

class LicenseSerializer(serializers.ModelSerializer):
    user=UserSerializer(read_only=True)
    is_valid=serializers.BooleanField(read_only=True)

    class Meta:
        model=License
        fields='__all__'

class LicenseValidationSerializer(serializers.Serializer):
    license_key=serializers.CharField(max_length=64)
    hardware_id=serializers.CharField(max_length=100,required=False)

class LicenseRenewalSerializer(serializers.Serializer):
    license_key=serializers.CharField(max_length=64)
    days=serializers.IntegerField(default=365)