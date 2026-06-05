from .base_provider import BaseProvider
from ...radar.mqtt_client import MqttClientHandler
import logging

log = logging.getLogger(__name__)

class MQTTProvider(BaseProvider):
    """
    Fornecedor de dados via MQTT.
    """
    def __init__(self, client_id, broker_ip, data_topic):
        self.mqtt_handler = MqttClientHandler(client_id, broker_ip)
        self.data_topic = data_topic
        self._buffer = []

    def connect(self):
        self.mqtt_handler.connect()
        self.mqtt_handler.client.subscribe(self.data_topic)
        self.mqtt_handler.client.on_message = self._on_message
        log.info(f"MQTTProvider subscrito em: {self.data_topic}")

    def _on_message(self, client, userdata, msg):
        # Apenas guardamos os bytes recebidos
        self._buffer.append(msg.payload)

    def read_data(self):
        """
        Retorna o pacote de dados mais antigo no buffer, ou None se vazio.
        """
        if self._buffer:
            return self._buffer.pop(0)
        return b''

    def disconnect(self):
        self.mqtt_handler.client.unsubscribe(self.data_topic)
        self.mqtt_handler.disconnect()
