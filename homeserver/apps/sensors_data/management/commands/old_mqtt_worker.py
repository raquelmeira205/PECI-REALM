from django.utils import timezone
import json
import paho.mqtt.client as mqtt
from django.core.management.base import BaseCommand
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from collections import deque
import time
from environments.models import Room, Home
from sensors_devices.models import Radar

class Command(BaseCommand):
    help = 'MQTT Worker with Real-time mapping of Sensors to Rooms'

    def handle(self, *args, **kwargs):
        self.channel_layer = get_channel_layer()
        self.buffers = {} 
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.stdout.write(self.style.WARNING('Worker Started: Waiting for "raw" data...'))

        try:
            self.client.connect("localhost", 1883, 60)
            
            self.client.loop_start() 
        
            while True:
                time.sleep(10) 
                
        except KeyboardInterrupt:
            self.client.loop_stop()
            self.stdout.write(self.style.SUCCESS('Worker stopped successfully.'))

    def on_connect(self, client, userdata, flags, rc, properties=None):
        self.stdout.write(self.style.SUCCESS(f'Connected to Broker! Code: {rc}'))
        client.subscribe("radar/+/raw")

    def on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split('/')

            if len(topic_parts) < 3:
                self.stderr.write(f"Invalid topic format: {msg.topic}")
                return
            
            serial_number = topic_parts[1]
            now = timezone.now()
            try:
                radar = Radar.objects.get(network_id=serial_number)
                
                # time since last seen for heartbeat and reconnection logic
                time_since_last = (now - radar.last_seen).total_seconds() if radar.last_seen else float('inf')

                # heartbeat throttle: only update DB if more than 3 seconds have passed since last update
                if time_since_last >= 3:
                    radar.is_online = True
                    radar.last_seen = now
                    radar.save(update_fields=['is_online', 'last_seen'])

                # reconnection logic: if radar was offline for more than 10 seconds and is not assigned to a room, trigger discovery
                is_reconnecting = time_since_last > 10
                
                if is_reconnecting and not radar.room:
                    async_to_sync(self.channel_layer.group_send)(
                        'available_radars',
                        {'type': 'radar_discovery'}
                    )
                
                if not radar.room:
                    return
                
                room_id = radar.room.id
                
            except Radar.DoesNotExist:
                # If radar is new, create it and trigger discovery for unassigned radars
                radar = Radar.objects.create(
                    network_id=serial_number, 
                    is_online=True, 
                    last_seen=now,
                    status=Radar.OperationalStatus.UNASSIGNED # Ensure new radars start as unassigned
                )
                
                async_to_sync(self.channel_layer.group_send)(
                    'available_radars',
                    {'type': 'radar_discovery'}
                )
                self.stdout.write(self.style.SUCCESS(f"New radar discovered: {serial_number}"))
                return

            # Process coordinates if payload is valid JSON and contains pointCloud
            try:
                payload = json.loads(msg.payload.decode())
            except json.JSONDecodeError:
                return
                
            points = payload.get('pointCloud', [])
            if not points: 
                return

            # Calculate raw averages for X and Y from the point cloud
            raw_x = sum(p[0] for p in points) / len(points)
            raw_y = sum(p[1] for p in points) / len(points)
            
            if room_id not in self.buffers:
                self.buffers[room_id] = {'x': deque(maxlen=5), 'y': deque(maxlen=5)}

            self.buffers[room_id]['x'].append(raw_x)
            self.buffers[room_id]['y'].append(raw_y)

            if len(self.buffers[room_id]['x']) >= 3:
                avg_x = sum(self.buffers[room_id]['x']) / len(self.buffers[room_id]['x'])
                avg_y = sum(self.buffers[room_id]['y']) / len(self.buffers[room_id]['y'])

                async_to_sync(self.channel_layer.group_send)(
                    f'room_{room_id}',
                    {
                        'type': 'radar_message',
                        'data': {
                            'x': round(avg_x, 3),
                            'y': round(avg_y, 3),
                            'radar_sn': serial_number,
                            'room_name': radar.room.name,
                            'timestamp': now.strftime('%H:%M:%S')
                        },
                    }
                )

        except Exception as e:
            self.stderr.write(f"Error processing: {e}")