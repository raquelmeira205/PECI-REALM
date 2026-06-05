# System Architecture

> This document provides an overview of the REALM system architecture.
> Expand with diagrams and detailed component descriptions as needed.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Home Server                          │
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐  ┌─────────┐  │
│  │ Django   │   │InfluxDB  │   │  Redis   │  │Mosquitto│  │
│  │ (Daphne) │◄──│(TS data) │   │(WS/cache)│  │(broker) │  │
│  └──────────┘   └──────────┘   └──────────┘  └────┬────┘  │
└───────────────────────────────────────────────────┼────────┘
                                                     │ MQTT
              ┌──────────────────────────────────────┼──────┐
              │                                      │      │
     ┌────────▼──────┐                    ┌──────────▼────┐ │
     │  Radar Node 1  │                    │  Radar Node N │ │
     │                │                    │               │ │
     │  Raspberry Pi  │        ...         │  Raspberry Pi │ │
     │  + IWR6843ODS  │                    │  + IWR6843ODS │ │
     └───────────────┘                    └───────────────┘
```

## Components

### Radar Node (`radar-node/`)

Each node is a Raspberry Pi connected to a TI IWR6843ODS mmWave radar via USB/UART.

- **`radar_manager.py`** — Boot-time lifecycle manager. Checks network connectivity, applies saved Wi-Fi credentials, launches `node_client.py` on success or `config_server.py` (AP captive portal) on failure.
- **`node_client.py`** — Main runtime process. Connects to the MQTT broker, sends heartbeats (`radar/{sn}/hello`), receives commands (`start`, `stop`, `ntp_sync`), and spawns `acquisition/stream_manager.py` as a subprocess.
- **`config_server.py`** — Captive portal HTTP server (port 8080). Served in AP mode to collect Wi-Fi and MQTT credentials from a phone/browser.
- **`ntp_service.py`** — NTP offset measurement used to confirm temporal alignment across nodes.
- **`acquisition/`** — Data acquisition sub-package. `stream_manager.py` reads serial frames from the radar (via `uart_provider.py`) and publishes point cloud / track data over MQTT.
- **`config/`** — Static configuration: MQTT topic schema (`topics.py`), radar profile (`ODS_6m_default.cfg`), room and sensor calibration JSON, and the systemd service unit.

### Home Server (`homeserver/`)

Django 4 application running in Docker Compose.

| Service | Role |
|---------|------|
| `web` (Daphne) | Serves the Django app over HTTP + WebSockets |
| `worker` | MQTT worker process (`mqtt_worker.py`) that bridges MQTT → InfluxDB |
| `influxdb` | Time-series storage for radar point cloud and track data |
| `redis` | Channel layer for Django Channels (WebSocket push) |
| `mosquitto` | MQTT broker receiving data from all radar nodes |

Key Django apps:

| App | Responsibility |
|-----|---------------|
| `core` | Shared geometry and data-filtering utilities |
| `sensors_devices` | Radar device registry and spatial calibration |
| `sensors_data` | MQTT ingestion, InfluxDB queries, data models |
| `deployment` | Step-by-step deployment wizard with live WebSocket progress |
| `dashboard` | Live and accumulated heatmap monitoring UI |
| `developer` | Synchronized multi-node data capture sessions |
| `environments` | Home / room management |
| `users` | Email-based authentication |
| `activity_summary` | Weekly activity summary views |
| `web_api` | REST API endpoints |

## MQTT Topic Schema

```
radar/{serial}/hello      # Node heartbeat — sent every 5 s
radar/{serial}/raw        # Raw point cloud / track payload (streaming)
radar/{serial}/status     # State confirmations (e.g. ntp_ok)
radar/{serial}/command    # Server → node commands: start | stop | ntp_sync
```

Wildcards used server-side: `radar/+/hello`, `radar/+/status`
