from rest_framework import serializers
from sensors_devices.models import Radar
from environments.models import Room

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'

class RadarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Radar
        fields = '__all__'
