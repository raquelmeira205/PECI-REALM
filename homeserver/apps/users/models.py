from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('E-mail is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'DEVELOPER')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser, BaseModel):
    username = None
    email = models.EmailField(unique=True)

    objects = CustomUserManager()

    class Role(models.TextChoices):
        RESIDENT = 'RESIDENT', 'Resident'
        CAREGIVER = 'CAREGIVER', 'Caregiver'
        DEVELOPER = 'DEVELOPER', 'Developer'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.RESIDENT)

    birth_date = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def clean(self):
        """ Birth date is mandatory for RESIDENT role """
        super().clean()
        if self.role == self.Role.RESIDENT and not self.birth_date:
            raise ValidationError('Birth date is required for Residents.')

    def save(self, *args, **kwargs):
        self.full_clean()  
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"