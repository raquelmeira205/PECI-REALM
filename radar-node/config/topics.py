class MqttTopics:
    # Tópicos padronizados de comunicação
    HELLO           = "radar/{serial}/hello"    # Heartbeat + descoberta
    DATA_RAW        = "radar/{serial}/raw"      # Telemetria (só com captura activa)
    STATUS          = "radar/{serial}/status"   # Confirmações de estado (ex: ntp_ok)
    COMMAND         = "radar/{serial}/command"  # Comandos: start, stop, ntp_sync

    # Wildcards para subscrição do lado do servidor (MQTT '+')
    HELLO_ALL       = "radar/+/hello"
    STATUS_ALL      = "radar/+/status"

    @classmethod
    def get_hello_topic(cls, serial):
        return cls.HELLO.format(serial=serial)

    @classmethod
    def get_data_topic(cls, serial):
        return cls.DATA_RAW.format(serial=serial)

    @classmethod
    def get_status_topic(cls, serial):
        return cls.STATUS.format(serial=serial)

    @classmethod
    def get_command_topic(cls, serial):
        return cls.COMMAND.format(serial=serial)
