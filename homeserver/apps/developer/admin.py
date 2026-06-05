from django.contrib import admin
from .models import AcquisitionSession, RadarFrame

admin.site.register(AcquisitionSession)
admin.site.register(RadarFrame)
