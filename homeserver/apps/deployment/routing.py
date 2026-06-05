from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://127.0.0.1:8000/ws/radar/1/
    re_path(r'ws/radar/(?P<room_id>\w+)/$', consumers.RadarConsumer.as_asgi()),
    re_path(r'ws/available-radars/', consumers.AvailableRadarsConsumer.as_asgi()),
]