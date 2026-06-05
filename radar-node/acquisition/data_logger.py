import json
import logging
from datetime import datetime
import os

log = logging.getLogger(__name__)

class DataLogger:
    """
    Responsável exclusivo por gravar as capturas para o disco, quer sejam
    brutas (raw bin) ou semi-processadas (se aplicável futuramente).
    """
    def __init__(self, base_dir="acquisitions"):
        self.base_dir = base_dir
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def log_raw_bytes(self, raw_bytes, prefix="raw_"):
        """
        Grava os bytes diretamente num ficheiro binário.
        Pode ser útil para debugging cru.
        """
        if not raw_bytes:
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.base_dir, f"{prefix}{timestamp}.bin")
        try:
            with open(filename, "ab") as f:
                f.write(raw_bytes)
            log.debug(f"Bytes gravados em {filename}")
        except Exception as e:
            log.error(f"Erro ao gravar dados brutos: {e}")
