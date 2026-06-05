# core/radar/ntp_service.py

import ntplib
import logging

log = logging.getLogger(__name__)

class NTPManager:
    """
    Serviço para verificar o sincronismo de relógios (NTP) entre as máquinas.
    Pode apontar para um servidor NTP local (ex: IP do Master) ou público.
    """
    def __init__(self, ntp_server="pool.ntp.org"):
        # Se tiverem os Raspberry Pis numa rede local sem internet, 
        # podes mudar isto para o IP estático do Raspberry Master (ex: "192.168.1.100")
        self.ntp_server = ntp_server
        self.client = ntplib.NTPClient()

    def get_offset_ms(self):
        """
        Comunica com o servidor NTP e devolve o desvio do relógio em milissegundos.
        Retorna o valor absoluto do offset ou None se a rede falhar.
        """
        try:
            # O timeout de 2 segundos evita que o Wizard fique encravado se a rede falhar
            response = self.client.request(self.ntp_server, version=3, timeout=2.0)
            
            # O atributo .offset vem em segundos. Convertendo para ms:
            offset_ms = response.offset * 1000.0
            return abs(offset_ms)
            
        except Exception as e:
            log.error(f"Falha ao conectar ao servidor NTP {self.ntp_server}: {e}")
            return None