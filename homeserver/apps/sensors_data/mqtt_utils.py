import mqtt, os, json

def publish_radar_command(radar_sn: str, command: str) -> None:
    """Publica um comando a um radar via MQTT (conexão de curta duração)."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    broker = os.getenv("MQTT_BROKER_HOST", "mosquitto")
    client.connect(broker, 1883, 60)
    payload = json.dumps({"command": command})
    client.publish(f"radar/{radar_sn}/command", payload)
    client.disconnect()