from django.db import models
from django.contrib.auth.models import User
import secrets
import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from datetime import timedelta
from django.utils import timezone

class License(models.Model):
    LICENSE_STATUS=[
        ('active','Active'),
        ('expired','Expired'),
        ('revoked','Revoked')
    ]
    key=models.CharField(max_length=500) 
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='licenses')
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField()
    status=models.CharField(max_length=20, choices=LICENSE_STATUS,default='active')
    hardware_id=models.CharField(max_length=100, blank=True,null=True)
    view_password_salt=models.CharField(max_length=64,blank=True,null=True)
    view_password_hash=models.CharField(max_length=128,blank=True,null=True)
    _decrypted_key_cache=None
    
    class Meta:
        verbose_name_plural="Licenses"
        
    def __str__(self):
        displayed_key_portion=self.displayed_key[:10]
        if len(self.displayed_key)>10:
            displayed_key_portion+='...'
        return (f"License for {self.user.email} (Status: {self.status}) - Key: {displayed_key_portion}")

    def _derive_fernet_key(self, raw_view_password):
        if not self.view_password_salt:
            return None
        kdf=PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.view_password_salt.encode('utf-8'),
            iterations=100000,
            backend=default_backend()
        )
        derived_key=base64.urlsafe_b64encode(kdf.derive(raw_view_password.encode('utf-8')))
        return Fernet(derived_key)

    def set_license_view_password_and_encrypt_key(self, raw_view_password, actual_license_key):
        self.view_password_salt=secrets.token_urlsafe(30) 
        self.view_password_hash=hashlib.pbkdf2_hmac(
            'sha256',
            raw_view_password.encode('utf-8'),
            self.view_password_salt.encode('utf-8'),
            100000 
        ).hex()
        fernet=self._derive_fernet_key(raw_view_password)
        self.key=fernet.encrypt(actual_license_key.encode('utf-8')).decode('utf-8')

    def decrypt_actual_key(self, raw_view_password):
        if not self.key or not self.view_password_salt or not self.view_password_hash:
            return None
        attempt_hash=hashlib.pbkdf2_hmac(
            'sha256',
            raw_view_password.encode('utf-8'),
            self.view_password_salt.encode('utf-8'),
            100000
        ).hex()
        if attempt_hash!=self.view_password_hash:
            return None
        fernet=self._derive_fernet_key(raw_view_password)
        try:
            decrypted_bytes=fernet.decrypt(self.key.encode('utf-8'))
            self._decrypted_key_cache=decrypted_bytes.decode('utf-8')
            return self._decrypted_key_cache
        except InvalidToken:
            print("Decryption failed: Invalid Token (maybe wrong password or wrong data format)")
            return None
        except Exception as e:
            print(f"Decryption error: {e}")
            return None

    @property
    def displayed_key(self):
        if self._decrypted_key_cache:
            return self._decrypted_key_cache
        return "XXXXXXXXXXXXX"

    @property
    def is_key_decrypted(self):
        return self._decrypted_key_cache is not None

    def save(self,*args,**kwargs):
        super().save(*args,**kwargs)

    @classmethod
    def generate_random_raw_key(cls):
        return f"LIC-{secrets.token_hex(12)}-{secrets.token_urlsafe(8)}"

    @property
    def is_valid(self):
        return (
            self.status=='active' and 
            self.expires_at>timezone.now()
        )

    def renew(self,days=365):
        self.expires_at+=timedelta(days=days)
        self.save()

class AdminSettings(models.Model):
    license_request_email=models.EmailField(
        verbose_name='License Request Email',
        #help_text="This email will receive all kinds of new license requests from users.",
        blank=True,
        null=True
    )
    class Meta:
        verbose_name='Admin Settings'
        verbose_name_plural='Admin Settings'
    
    def __str__(self):
        return "Admin Settings"