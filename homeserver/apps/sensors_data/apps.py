from django.apps import AppConfig
import threading
import sys
import os

from django.core.management import call_command


class SensorDataConfig(AppConfig):
    name = 'sensors_data'

    def ready(self):
        """Start the MQTT worker automatically when `runserver` runs.

        Guard against Django's autoreloader by only starting in the
        ``RUN_MAIN`` process (when environment variable RUN_MAIN is 'true').
        The worker is started in a daemon thread so it doesn't block
        the main process termination.
        """
        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') == 'true':
            def _start():
                try:
                    call_command('mqtt_worker')
                except Exception:
                    import logging
                    logging.exception('Falha ao iniciar mqtt_worker')

            t = threading.Thread(target=_start, name='mqtt_worker_thread', daemon=True)
            t.start()
