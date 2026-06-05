import os
import json
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from dotenv import load_dotenv

from django.utils import timezone
from django.core.management.base import BaseCommand
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import paho.mqtt.client as mqtt

# Importações do Projeto
from sensors_devices.models import Radar
from developer.models import AcquisitionSession, RadarFrame
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Carregar variáveis de ambiente (.env)
load_dotenv()

class Command(BaseCommand):
    help = 'MQTT Worker: Ingests Radar Data to InfluxDB and Django Channels'

    def handle(self, *args, **kwargs):
        self.channel_layer = get_channel_layer()
        
        # 1. Configuração Segura do InfluxDB (Lendo do .env)
        self.influx_url = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
        self.influx_token = os.getenv("INFLUXDB_TOKEN")
        self.influx_org = os.getenv("INFLUXDB_ORG")
        self.influx_bucket = os.getenv("INFLUXDB_BUCKET")

        if not self.influx_token:
            self.stderr.write(self.style.ERROR("ERRO: INFLUXDB_TOKEN não encontrado no .env"))
            return

        self.influx_client = InfluxDBClient(
            url=self.influx_url, 
            token=self.influx_token, 
            org=self.influx_org
        )
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        
        # 2. Configuração MQTT
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.stdout.write(self.style.WARNING('🚀 Worker Iniciado: A aguardar dados dos radares...'))

        try:
            broker_ip = os.getenv("MQTT_BROKER_HOST", "mosquitto")
            self._connect_with_retry(broker_ip)
            self.client.loop_forever() 
        except KeyboardInterrupt:
            self.influx_client.close()
            self.stdout.write(self.style.SUCCESS('\nWorker parado com sucesso.'))

    def _connect_with_retry(self, broker_ip):
        max_attempts = int(os.getenv("MQTT_CONNECT_RETRIES", "30"))
        retry_delay = float(os.getenv("MQTT_CONNECT_DELAY_SECONDS", "2"))

        for attempt in range(1, max_attempts + 1):
            try:
                self.client.connect(broker_ip, 1883, 60)
                return
            except Exception as exc:
                if attempt == max_attempts:
                    raise
                self.stdout.write(
                    self.style.WARNING(
                        f"A aguardar o broker MQTT em {broker_ip}:1883 ({attempt}/{max_attempts}) - {exc}"
                    )
                )
                time.sleep(retry_delay)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        self.stdout.write(self.style.SUCCESS(f'✅ Ligado ao Broker MQTT!'))
        client.subscribe("radar/+/hello")
        client.subscribe("radar/+/raw")
        client.subscribe("radar/+/status")

    def on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split('/')
            serial_number = topic_parts[1]
            msg_type = topic_parts[2]
            now = timezone.now()

            if msg_type == 'hello':
                self._handle_hello_message(serial_number, now)
            elif msg_type == 'raw':
                self._handle_raw_message(serial_number, msg, now)
            elif msg_type == 'status':
                payload = json.loads(msg.payload.decode())
                self._handle_status_message(serial_number, payload, now)

        except Exception as e:
            self.stderr.write(f"❌ Erro ao processar mensagem ({msg.topic}): {e}")

    def _handle_hello_message(self, serial_number, now):
        """Auto-discovery e heartbeat do radar via tópico hello."""
        radar, created = Radar.objects.get_or_create(
            network_id=serial_number,
            defaults={'is_online': True, 'last_seen': now, 'status': Radar.OperationalStatus.UNASSIGNED},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'🆕 Novo radar descoberto: {serial_number}'))
            async_to_sync(self.channel_layer.group_send)('available_radars', {'type': 'radar_discovery'})
        elif not radar.last_seen or (now - radar.last_seen).total_seconds() > 3:
            reconnected = not radar.last_seen or (now - radar.last_seen).total_seconds() > 30
            radar.is_online = True
            radar.last_seen = now
            radar.save(update_fields=['is_online', 'last_seen'])
            if reconnected and radar.is_calibrated:
                self._publish_command(serial_number, 'start')
                self.stdout.write(self.style.SUCCESS(f'▶ Start enviado a {serial_number} (reconexão)'))

    def _handle_status_message(self, serial_number, payload, now):
        status = payload.get('status')
        if status != 'ntp_ok':
            return

        try:
            radar = Radar.objects.select_related('room').get(network_id=serial_number)
        except Radar.DoesNotExist:
            return

        if not radar.room:
            return

        radar.status = Radar.OperationalStatus.ACTIVE
        radar.save(update_fields=['status'])
        self.stdout.write(self.style.SUCCESS(f'✅ NTP OK de {serial_number}'))

        # Notifica o browser em tempo real para atualizar o badge do slave
        async_to_sync(self.channel_layer.group_send)(
            f'room_{radar.room.id}',
            {
                'type': 'sync_status',
                'radar_sn': serial_number,
            }
        )
    
    def _handle_raw_message(self, serial_number, msg, now):
        """Processa batch de frames de telemetria e escreve no InfluxDB."""
        try:
            radar = Radar.objects.select_related('room__home').get(network_id=serial_number)
        except Radar.DoesNotExist:
            self.stderr.write(f"⚠ Radar não encontrado na BD: {serial_number}")
            return

        if not radar.room:
            self.stderr.write(f"⚠ Radar {serial_number} sem sala atribuída — ignorado")
            return

        active_sessions = list(AcquisitionSession.objects.filter(radar=radar, ended_at__isnull=True))

        payload = json.loads(msg.payload.decode())
        frames = payload if isinstance(payload, list) else [payload]

        points_to_write = []
        db_frames_to_create = []
        last_targets = []
        last_point_cloud = []
        last_dt = now

        n_frames = len(frames)
        for i, frame in enumerate(frames):
            metadata = frame.get("metadata", {})
            radar_data = frame.get("data") or frame.get("radar_data", {})

            # Use UTC-aware timestamps derived from `now` (always UTC from Django).
            # The raspberry sends naive local timestamps (datetime.now()) which influxdb-client
            # misinterprets as UTC, storing data 1 hour in the future (Portugal = UTC+1).
            # Distribute frame timestamps evenly across the last 600ms of the batch window.
            dt_ts = now - timedelta(milliseconds=(n_frames - 1 - i) * 60)
            targets = radar_data.get("targets", [])

            for target in targets:
                point = Point("radar_data") \
                    .tag("room_id", str(radar.room.id)) \
                    .tag("home_id", str(radar.room.home.id)) \
                    .tag("radar_sn", serial_number) \
                    .tag("target_id", str(target.get("target_id", "0"))) \
                    .field("x", float(target["position"]["x"])) \
                    .field("y", float(target["position"]["y"])) \
                    .field("z", float(target["position"]["z"])) \
                    .time(dt_ts, WritePrecision.NS)
                points_to_write.append(point)

            last_targets = targets
            last_point_cloud = radar_data.get("raw_point_cloud", [])
            last_dt = dt_ts

            for pt in last_point_cloud:
                if len(pt) >= 5:
                    point = Point("radar_raw_pc") \
                        .tag("radar_sn", serial_number) \
                        .field("x",       float(pt[0])) \
                        .field("y",       float(pt[1])) \
                        .field("z",       float(pt[2])) \
                        .field("doppler", float(pt[3])) \
                        .field("snr",     float(pt[4])) \
                        .time(dt_ts, WritePrecision.NS)
                    points_to_write.append(point)

            if active_sessions:
                track_data = []
                for t in targets:
                    tid = t.get("target_id", 0)
                    pos = t.get("position", {})
                    vel = t.get("velocity", {})
                    track_data.append([
                        tid,
                        float(pos.get("x", 0.0)), float(pos.get("y", 0.0)), float(pos.get("z", 0.0)),
                        float(vel.get("x", 0.0)), float(vel.get("y", 0.0)), float(vel.get("z", 0.0))
                    ])

                frame_number = metadata.get("frame", 0)
                num_points = len(last_point_cloud)
                num_tracks = len(targets)
                
                for session in active_sessions:
                    db_frames_to_create.append(
                        RadarFrame(
                            session=session,
                            frame_number=frame_number,
                            timestamp=dt_ts,
                            num_detected_points=num_points,
                            num_detected_tracks=num_tracks,
                            point_cloud=last_point_cloud,
                            track_data=track_data
                        )
                    )

        if db_frames_to_create:
            try:
                RadarFrame.objects.bulk_create(db_frames_to_create)
            except Exception as e:
                self.stderr.write(f"❌ Erro ao guardar RadarFrames no SQLite: {e}")

        async_to_sync(self.channel_layer.group_send)(
            f'room_{radar.room.id}',
            {
                'type': 'radar_message',
                'data': {
                    'targets': last_targets,
                    'point_cloud': last_point_cloud,
                    'radar_sn': serial_number,
                    'timestamp': last_dt.strftime('%H:%M:%S'),
                },
            }
        )

        if points_to_write:
            try:
                self.write_api.write(bucket=self.influx_bucket, record=points_to_write)
                self.stdout.write(f"📥 {serial_number}: {len(points_to_write)} pontos escritos no InfluxDB")
            except Exception as e:
                self.stderr.write(f"❌ Erro ao escrever no InfluxDB ({serial_number}): {e}")
        else:
            self.stdout.write(f"📡 {serial_number}: batch recebido ({len(frames)} frames, 0 targets)")

    def _publish_command(self, radar_sn, command):
        """Publica um comando a um radar via MQTT."""
        self.client.publish(f"radar/{radar_sn}/command", json.dumps({"command": command}))