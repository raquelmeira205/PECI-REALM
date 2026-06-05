import serial
import time
import platform
import logging
from serial.tools import list_ports

# Tentamos importar do root se o script for corrido a partir de lá
try:
    from demo_defines import *
except ImportError:
    # Fallback caso seja corrido isoladamente
    CLI_XDS_SERIAL_PORT_NAME = "XDS110 Class Application/User UART"
    DATA_XDS_SERIAL_PORT_NAME = "XDS110 Class Auxiliary Data Port"
    CLI_SIL_SERIAL_PORT_NAME = "Silicon Labs CP210x USB to UART Bridge"
    DATA_SIL_SERIAL_PORT_NAME = "Silicon Labs Dual CP210x USB to UART Bridge: Enhanced COM Port"
    TI_XDS110_VID = 0x0451
    TI_XDS110_PID = 0xbef3

from .base_provider import BaseProvider

log = logging.getLogger(__name__)

class UARTProvider(BaseProvider):
    """
    Fornecedor de dados via Porta Série (UART).
    Comporta-se como um "Dumb Pipe" para extrair raw bytes ininterruptamente.
    """
    def __init__(self, device="xWR6843", chunk_size=1024):
        self.device = device
        self.chunk_size = chunk_size
        self.cliCom = None
        self.dataCom = None

    def connect(self):
        uart_port, data_port = self._find_ports()
        if not uart_port or not data_port:
            raise Exception("Port(s) not found! Please check the connection.")

        self._connect_ports(uart_port, data_port)

    def _find_ports(self):
        serialPorts = list(list_ports.comports())
        uart = None
        data = None

        if platform.system() == "Windows":
            for port in serialPorts:
                if CLI_XDS_SERIAL_PORT_NAME in port.description or CLI_SIL_SERIAL_PORT_NAME in port.description:
                    log.info(f"CLI COM Port found: {port.device}")
                    uart = port.device
                elif DATA_XDS_SERIAL_PORT_NAME in port.description or DATA_SIL_SERIAL_PORT_NAME in port.description:
                    log.info(f"Data COM Port found: {port.device}")
                    data = port.device
        else:
            xds_ports = sorted([p for p in serialPorts if p.vid == TI_XDS110_VID and p.pid == TI_XDS110_PID], key=lambda p: p.device)
            if len(xds_ports) >= 2:
                uart = xds_ports[0].device
                data = xds_ports[1].device
                log.info(f"CLI COM Port found: {uart}")
                log.info(f"Data COM Port found: {data}")

        return uart, data

    def _connect_ports(self, cliCom, dataCom):
        if self.device == "xWR6843":
            self.cliCom = serial.Serial(cliCom, 115200, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.6)
            self.dataCom = serial.Serial(dataCom, 921600, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.6)
            self.dataCom.reset_output_buffer()
            self._soft_reset()
            log.info('Connected to xWR6843')
        elif self.device == "xWRL6844":
            self.cliCom = serial.Serial(cliCom, 115200, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.6)
            self.dataCom = serial.Serial(dataCom, 1250000, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.6)
            self.dataCom.reset_output_buffer()
            self._soft_reset()
            log.info('Connected to xWRL6844')
        else:
            raise Exception("Device not supported by UARTProvider currently.")

    def _soft_reset(self):
        log.info("A enviar Hard Reset via software...")
        try:
            self.cliCom.write(b'\n')
            time.sleep(0.1)
            self.cliCom.write(b'resetDevice\n')
            time.sleep(2.0)
            self.cliCom.reset_input_buffer()
            self.cliCom.reset_output_buffer()
            if self.dataCom:
                while self.dataCom.in_waiting > 0:
                    self.dataCom.read(self.dataCom.in_waiting)
                    time.sleep(0.01)
                self.dataCom.reset_input_buffer()
                self.dataCom.reset_output_buffer()
            log.info("Soft reset concluído com sucesso.")
        except Exception as e:
            log.error(f"Erro no soft reset: {e}")

    def send_config(self, cfg_lines):
        # Remove empty lines from the cfg
        cfg = [line for line in cfg_lines if line != '\n']
        # Ensure \n at end of each line
        cfg = [line + '\n' if not line.endswith('\n') else line for line in cfg]
        # Remove commented lines
        cfg = [line for line in cfg if line[0] != '%']

        for line in cfg:
            time.sleep(.03)
            self.cliCom.write(line.encode())
            ack = self.cliCom.readline()
            if len(ack) == 0:
                log.error("ERROR: No data detected on COM Port, read timed out")
                return False
            
            ack = self.cliCom.readline()
            splitLine = line.split()
            if splitLine[0] == "baudRate":
                try:
                    self.cliCom.baudrate = int(splitLine[1])
                except:
                    log.error("Error - Invalid baud rate")

        time.sleep(0.03)
        self.cliCom.reset_input_buffer()
        return True

    def read_data(self):
        """
        Dumb Pipe: Lê exatamente o que estiver no buffer da dataCom 
        ou espera pelo menos a leitura de 1 byte.
        """
        if self.dataCom is None:
            raise Exception("UART Data Port not initialized.")
        
        # Leitura bloqueante que espera até haver algum byte (devido ao timeout configurado)
        # Lê até 'chunk_size' bytes.
        raw_bytes = self.dataCom.read(self.chunk_size)
        return raw_bytes

    def disconnect(self):
        try:
            time.sleep(1)
            if self.cliCom and self.cliCom.is_open:
                self.cliCom.write(b'sensorStop\n')
                time.sleep(0.1)
                self.cliCom.close()
            if self.dataCom and self.dataCom.is_open:
                self.dataCom.close()
            log.info("Portas série fechadas com segurança.")
        except Exception as e:
            log.error(f"Erro ao fechar portas: {e}")
