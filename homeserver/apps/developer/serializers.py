from rest_framework import serializers
from .models import AcquisitionSession, RadarFrame

class AcquisitionSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcquisitionSession
        fields = '__all__'

class RadarFrameSerializer(serializers.ModelSerializer):
    class Meta:
        model = RadarFrame
        fields = '__all__'