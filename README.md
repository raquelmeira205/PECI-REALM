# REALM — Radar-based Easy-deploy And Low-intrusive Monitoring

REALM is a privacy-preserving low-intrusive indoor human monitoring system built for smart home and elderly care applications. It uses Texas Instruments IWR6843ODS mmWave radar sensors deployed as wireless edge nodes to detect and track occupant presence, movement, and activity patterns, without cameras or microphones. Sensor data flows over MQTT from each Raspberry Pi node to a central Django-based home server, where it is stored in InfluxDB and visualised through a live web dashboard.

Developed at the University of Aveiro as part of the PECI course, in the context of the Casa Viva+ and VITALITY smart home research projects.

---

## System Architecture

```
  Radar Node(s)                      Home Server (Docker)
  ─────────────────                  ───────────────────────────────────────
  IWR6843ODS radar                   ┌─────────┐   ┌──────────┐
       │ USB/UART                    │Mosquitto│   │ InfluxDB │
  Raspberry Pi                       │(broker) │   │(TS data) │
  ├─ stream_manager.py               └────┬────┘   └────┬─────┘
  │    └─ publishes point cloud           │              │
  │       + track data via MQTT      ┌────▼──────────────▼─────┐
  ├─ node_client.py                  │   Django + Daphne (web)  │
  │    └─ heartbeat, commands        │   mqtt_worker (worker)   │
  └─ radar_manager.py                │   Redis (WebSockets)     │
       └─ boot lifecycle,            └──────────────────────────┘
          Wi-Fi provisioning                    │
                                         Web Dashboard
                           (heatmaps, deployment wizard, developer mode)
```

Data path: `radar/{serial}/raw` → MQTT worker → InfluxDB → WebSocket → browser.

---

## Hardware Requirements

| Component | Details |
|-----------|---------|
| Radar sensor | Texas Instruments IWR6843ODS (mmWave, 60 GHz) |
| Edge compute | Raspberry Pi (3B+ or later recommended) |
| Connectivity | Wi-Fi (2.4 GHz) to the same LAN as the home server |
| Server | Any Linux machine capable of running Docker Compose |

One Raspberry Pi + IWR6843ODS unit constitutes one radar node. Multiple nodes can be deployed simultaneously for multi-room coverage.

---

## Repository Structure

```
PECI-REALM/
├── homeserver/          Django home server — web dashboard, MQTT ingestion, InfluxDB
│   ├── apps/            Django applications (see below)
│   ├── radar_project/   Django project config (settings, URLs, ASGI/WSGI)
│   ├── templates/       HTML templates (HTMX-driven)
│   ├── static/          CSS, JS, calibration images
│   ├── mosquitto/       Mosquitto broker configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── manage.py
├── radar-node/          Raspberry Pi node software
│   ├── radar_manager.py Boot lifecycle manager (Wi-Fi, AP fallback)
│   ├── node_client.py   MQTT client -> heartbeat, command handling
│   ├── config_server.py Captive portal HTTP server (AP/provisioning mode)
│   ├── mqtt_client.py   Reusable MQTT publish/subscribe abstraction
│   ├── ntp_service.py   NTP offset measurement
│   ├── acquisition/     Data acquisition sub-package (UART serial reader)
│   ├── config/          Static config: radar profile, room/sensor JSON, topics, systemd unit
│   └── requirements.txt
├── docs/
│   └── architecture.md  Detailed component and data-flow documentation
└── README.md
```

### Django apps (`homeserver/apps/`)

| App | Responsibility |
|-----|---------------|
| `core` | Shared geometry transformations and data-filtering utilities |
| `sensors_devices` | Radar device registry and spatial calibration (Nelder-Mead) |
| `sensors_data` | MQTT ingestion, InfluxDB write/query, data models |
| `deployment` | Step-by-step deployment wizard with live WebSocket progress |
| `dashboard` | Live + accumulated heatmap monitoring UI |
| `developer` | Synchronized multi-node offline data capture sessions |
| `environments` | Home and room management |
| `users` | Email-based authentication |
| `activity_summary` | Weekly activity reports |
| `web_api` | REST API endpoints |

---

## Getting Started

### Home Server

**Prerequisites:** Docker and Docker Compose installed on the server machine.

**1. Clone and configure**

```bash
git clone <repo-url>
cd PECI-REALM/homeserver
cp .env.example .env
```

Edit `.env` and set at minimum:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key (generate a random string for production) |
| `DEBUG` | `True` for development, `False` for production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames/IPs the server is reachable on |
| `INFLUXDB_TOKEN` | Token for InfluxDB authentication |
| `INFLUXDB_ORG` | InfluxDB organisation name |
| `INFLUXDB_BUCKET` | InfluxDB bucket for sensor data |

The remaining variables (`REDIS_URL`, `MQTT_BROKER_HOST`) are pre-configured for the Docker network and do not need to change in a standard deployment.

**2. Start all services**

```bash
docker compose up -d
```

This starts five containers: `mosquitto` (MQTT broker), `influxdb` (time-series DB), `redis` (WebSocket channel layer), `web` (Django + Daphne), and `worker` (MQTT → InfluxDB bridge).

**3. Create a superuser**

```bash
docker compose exec web python manage.py createsuperuser
```

**4. Open the dashboard**

Navigate to `http://<server-ip>:8000` in a browser. Log in with the superuser credentials.

---

### Radar Node (Raspberry Pi)

**Prerequisites:** Raspberry Pi OS Lite, Python 3.9+, IWR6843ODS connected via USB.

**1. Copy the node software onto the Pi**

```bash
scp -r radar-node/ pi@<pi-ip>:/home/pi/realm-node
```

**2. Install dependencies**

```bash
cd /home/pi/realm-node
pip3 install -r requirements.txt
```

**3. Configure the node**

Edit `config/sensor_config.json` with the MQTT broker IP and the serial number for this node:

```json
{
  "serial": "SN_node01",
  "mqtt_ip": "192.168.1.50",
  "mqtt_port": 1883
}
```

**4. Run the lifecycle manager**

```bash
python3 radar_manager.py
```

On boot, `radar_manager.py` checks for internet connectivity. If the network is reachable, it launches `node_client.py` (normal operation). If no network is found after 60 seconds, it switches the Pi into AP mode and starts `config_server.py`.

**5. Install as a systemd service (optional)**

```bash
sudo cp config/radar_manager.service /etc/systemd/system/
sudo systemctl enable radar_manager
sudo systemctl start radar_manager
```

#### AP Mode / Auto-provisioning

If the Pi cannot reach the internet on boot, it creates a Wi-Fi access point. Connect a phone or laptop to that AP and open a browser, you will be redirected to a captive portal where you can enter the Wi-Fi SSID, password, and MQTT broker IP. On save, the Pi reboots and uses those credentials to join the network.

---

## Key Features

- **Semi-automatic multi-radar spatial calibration** -> Nelder-Mead optimisation aligns multiple sensors into a shared coordinate frame. A step-by-step wizard in the dashboard guides the installer.
- **NTP-based temporal synchronisation** -> Each node reports its NTP offset on demand; the server triggers sync before developer-mode capture sessions to ensure frame timestamps are aligned.
- **Deployment wizard** -> A guided, non-technical installer flow with live progress feedback over WebSockets. Handles device discovery, configuration, calibration, and validation.
- **Live + accumulated heatmaps** -> The monitoring dashboard shows both real-time occupancy heatmaps and historical presence density overlaid on the room layout.
- **Developer mode** -> Coordinated multi-node data acquisition: the server sends simultaneous `start`/`stop` commands and records raw radar streams for offline analysis.
- **Auto-provisioning (AP fallback)** -> Zero-configuration first-boot experience. Nodes self-identify their network state and present a captive portal when unconfigured.

---

## Configuration Reference

### Environment variables (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | — | Django secret key |
| `DEBUG` | `True` | Enable Django debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,web` | Allowed hostnames |
| `INFLUXDB_INIT_USERNAME` | `admin` | InfluxDB admin username |
| `INFLUXDB_INIT_PASSWORD` | — | InfluxDB admin password |
| `INFLUXDB_ORG` | `radar_project` | InfluxDB organisation |
| `INFLUXDB_BUCKET` | `sensors_data` | InfluxDB bucket |
| `INFLUXDB_TOKEN` | — | InfluxDB API token |
| `REDIS_URL` | `redis://redis:6379/1` | Redis connection URL |
| `MQTT_BROKER_HOST` | `mosquitto` | MQTT broker hostname |

### MQTT topic schema

```
radar/{serial}/hello      Node heartbeat, published every 5 s for discovery
radar/{serial}/raw        Streaming point cloud + track data (active capture only)
radar/{serial}/status     State confirmations from node  (e.g. {"status": "ntp_ok"})
radar/{serial}/command    Server → node commands:  start | stop | ntp_sync
```

Server subscribes to wildcards `radar/+/hello` and `radar/+/status` for fleet management.

---

## Academic Context

This project was developed as part of the **PECI** (Projeto em Engenharia de Computadores e Informática) programme at the **University of Aveiro**, in collaboration with the **Casa Viva+** and **VITALITY** smart home research initiatives. The goal is to support low-intrusive, privacy-respecting monitoring of elderly residents in assisted-living environments, enabling activity recognition and anomaly detection without cameras.

---

## Authors

- Ellen Sales — University of Aveiro
- Isabela Pereira — University of Aveiro
- Íris Biaguê — University of Aveiro
- Joana Santiago — University of Aveiro
- Raquel Meira — University of Aveiro
