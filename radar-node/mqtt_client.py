import json
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import logging

log = logging.getLogger(__name__)

class MqttClientHandler:
    """
    Classe genérica para ligar ao broker MQTT e lidar com a publicação.
    Abstrai os clientes MQTT.
    """
    def __init__(self, client_id, broker_ip, port=1883):
        self.client_id = client_id
        self.broker_ip = broker_ip
        self.port = port
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2, self.client_id)
        self._connected = False

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.on_message_callback = None

    def set_on_message_callback(self, callback):
        """
        Define a função a ser chamada quando uma mensagem é recebida.
        A função deve aceitar (client, userdata, message).
        """
        self.on_message_callback = callback

    def _on_message(self, client, userdata, message):
        if self.on_message_callback:
            self.on_message_callback(client, userdata, message)
        else:
            log.debug(f"[{self.client_id}] Recebido em {message.topic}: {message.payload}")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            log.info(f"[{self.client_id}] Conectado ao broker MQTT {self.broker_ip}")
            self._connected = True
        else:
            log.error(f"[{self.client_id}] Falha ao conectar. Código de erro: {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        log.warning(f"[{self.client_id}] Desconectado do broker MQTT.")
        self._connected = False

    def connect(self):
        try:
            self.client.connect(self.broker_ip, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            log.error(f"Erro crítico ao ligar ao MQTT Broker ({self.broker_ip}): {e}")
            raise e

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic, payload):
        if self._connected:
            if isinstance(payload, dict) or isinstance(payload, list):
                payload = json.dumps(payload)
            self.client.publish(topic, payload)
        else:
            log.warning("Tentativa de publicação sem estar conectado.")

    def subscribe(self, topic, qos=0):
        if self._connected:
            self.client.subscribe(topic, qos=qos)
            log.info(f"[{self.client_id}] Subscrito no tópico {topic}")
        else:
            log.warning(f"[{self.client_id}] Tentativa de subscrição em {topic} sem estar conectado.")
