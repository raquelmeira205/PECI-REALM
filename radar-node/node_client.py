import os
import json
import time
import socket
import threading
import subprocess
import logging
from mqtt_client import MqttClientHandler
from config.topics import MqttTopics
from ntp_service import NTPManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

CONFIG_FILE = "/home/rasp2/sensor_config.json"
RADAR_SCRIPT = "/home/rasp2/PECI-Low_Intrusive_Human_Monitoring_in_Smart_Spaces_Using_Radars/projeto/core/acquisition/stream_manager.py"

class NodeClient:
    def __init__(self):
        self.config = self._load_config()
        self.serial = self.config.get("serial", f"SN_{socket.gethostname()}")
        self.client_id = f"node_{self.serial}"

        self.mqtt_ip = self.config.get("mqtt_ip", "127.0.0.1")
        self.mqtt_port = self.config.get("mqtt_port", 1883)

        self.hello_topic  = MqttTopics.get_hello_topic(self.serial)
        self.status_topic = MqttTopics.get_status_topic(self.serial)
        self.cmd_topic    = MqttTopics.get_command_topic(self.serial)

        self.mqtt = MqttClientHandler(self.client_id, self.mqtt_ip, self.mqtt_port)
        self.mqtt.set_on_message_callback(self._on_message)

        self.stream_process = None
        self.running = True

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"Erro ao ler config: {e}")
        return {}

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode('utf-8'))
            cmd = payload.get("command", "")

            log.info(f"Comando recebido: {cmd}")

            if cmd == "start":
                log.info("Recebido comando para iniciar a stream.")
                self._start_stream()

            elif cmd == "stop":
                log.info("Recebido comando para parar a stream.")
                self._stop_stream()

            elif cmd == "ntp_sync":
                log.info("Recebido comando de sincronização NTP.")
                self._do_ntp_sync()

        except json.JSONDecodeError:
            log.warning(f"Payload não é JSON válido: {message.payload}")

    def _start_stream(self):
        if self.stream_process is None or self.stream_process.poll() is not None:
            log.info("A iniciar stream_manager.py...")
            self.stream_process = subprocess.Popen(["python3", RADAR_SCRIPT])
        else:
            log.info("A stream já está a correr.")

    def _stop_stream(self):
        if self.stream_process and self.stream_process.poll() is None:
            log.info("A parar stream_manager.py...")
            self.stream_process.terminate()
            self.stream_process.wait()
            self.stream_process = None

    def _do_ntp_sync(self):
        """Executa sincronização NTP e publica resultado no tópico de status."""
        ntp = NTPManager()
        offset = ntp.get_offset_ms()
        if offset is not None:
            log.info(f"NTP sync OK. Desvio: {offset:.2f} ms")
            self.mqtt.publish(self.status_topic, {"status": "ntp_ok"})
        else:
            log.error("NTP sync falhou — servidor NTP inacessível.")

    def _hello_loop(self):
        """Envia heartbeat periódico de 5s para descoberta pelo servidor."""
        while self.running:
            if self.mqtt._connected:
                msg = {"serial": self.serial}
                self.mqtt.publish(self.hello_topic, msg)
                log.debug(f"Hello enviado para {self.hello_topic}")
            time.sleep(5.0)

    def start(self):
        log.info(f"A iniciar NodeClient [{self.serial}]. Broker: {self.mqtt_ip}:{self.mqtt_port}")

        retry_delay = 2
        while self.running:
            try:
                self.mqtt.connect()
                break
            except Exception as e:
                log.warning(f"Falha ao conectar ao MQTT: {e}. A tentar de novo em {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

        # Espera pela conexão estar finalizada internamente
        timeout = 10
        while not self.mqtt._connected and timeout > 0:
            time.sleep(1)
            timeout -= 1

        if self.mqtt._connected:
            self.mqtt.subscribe(self.cmd_topic)

            hello_thread = threading.Thread(target=self._hello_loop, daemon=True)
            hello_thread.start()

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                log.info("Encerrando NodeClient...")
        else:
            log.error("Não foi possível conectar ao MQTT.")

        self.stop()

    def stop(self):
        self.running = False
        self._stop_stream()
        self.mqtt.disconnect()

if __name__ == "__main__":
    node = NodeClient()
    node.start()
