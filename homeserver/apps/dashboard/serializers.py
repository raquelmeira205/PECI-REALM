from rest_framework import serializers
from .models import ActivitySummary

class ActivitySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivitySummary
        fields = '__all__'