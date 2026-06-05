from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from environments.models import Room
from sensors_devices.models import Radar
from .serializers import RoomSerializer, RadarSerializer

class RoomCreateView(APIView):
    def post(self, request):
        serializer = RoomSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RadarSetupView(APIView):
    def post(self, request):
        network_id = request.data.get('network_id')
        # creates a new radar if it doesn't exist, otherwise updates the existing one
        radar, created = Radar.objects.get_or_create(
            network_id=network_id,
            defaults={'status': Radar.OperationalStatus.UNASSIGNED}
        )
        
        serializer = RadarSerializer(radar, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)