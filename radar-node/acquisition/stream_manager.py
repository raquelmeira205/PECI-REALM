import time
import logging
from providers.uart_provider import UARTProvider
# from providers.mqtt_provider import MQTTProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

class StreamManager:
    """
    O "Maestro" da Aquisição.
    Decide qual provider usar (UART ou MQTT) e entra num loop infinito de recolha de pacotes.
    """
    def __init__(self, provider_type="uart", **kwargs):
        self.provider_type = provider_type
        if self.provider_type == "uart":
            self.provider = UARTProvider(device=kwargs.get("device", "xWR6843"))
        elif self.provider_type == "mqtt":
            # Exemplo de instância do MQTTProvider, atualmente não testado no debugging
            # self.provider = MQTTProvider(client_id="stream_mgr", broker_ip="localhost", data_topic="radar/sensor1/raw")
            pass
        else:
            raise ValueError(f"Provider {provider_type} não suportado.")

    def run_debug_loop(self, config_file=None):
        """
        Debugging Independente: Loop ininterrupto que apenas recolhe e faz print do tamanho.
        """
        log.info(f"Iniciando StreamManager com provider: {self.provider_type}")
        
        self.provider.connect()
        
        if self.provider_type == "uart" and config_file:
            log.info(f"Enviando configuração a partir de: {config_file}")
            try:
                with open(config_file, "r") as f:
                    cfg_lines = f.readlines()
                self.provider.send_config(cfg_lines)
            except Exception as e:
                log.error(f"Erro ao carregar ou enviar configuração: {e}")
                self.provider.disconnect()
                return

        log.info("Entrando no loop de aquisição de raw bytes... (Pressione Ctrl+C para parar)")
        try:
            while True:
                raw_bytes = self.provider.read_data()
                if raw_bytes:
                    tamanho = len(raw_bytes)
                    print(f"Byte Array de tamanho {tamanho} recolhido")
                
                # Pequeno sleep para evitar consumir 100% CPU em caso de não bloqueio absoluto
                time.sleep(0.01)

        except KeyboardInterrupt:
            log.info("\nInterrupção solicitada pelo utilizador.")
        finally:
            log.info("Encerrando conexões...")
            self.provider.disconnect()

if __name__ == "__main__":
    # Exemplo de chamada direta para debugging independente
    # Assumindo que corres isto na raiz de 'projeto/core/acquisition/' ou passas path absoluta
    # cfg_path = "../../ODS_6m_default.cfg"
    import sys
    import os
    cfg_path = os.path.join(os.path.dirname(__file__), '../../ODS_6m_default.cfg')
    
    manager = StreamManager(provider_type="uart")
    manager.run_debug_loop(config_file=cfg_path)
