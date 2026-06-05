# Radar Project (PECI M3)

This project was developed in Django and its main goal is to enable dynamic registration, auto-discovery, and real-time monitoring of occupancy radars via *WebSockets* and *MQTT*.

The architecture includes an interactive **Frontend** powered by HTMX, a **Django Server** with WebSocket support (Django Channels), an **MQTT Worker** that ingests telemetry data from the radars, a **Time-Series Database (InfluxDB)** for historical telemetry persistence, and a **Real-Time Cache (Redis)** for asynchronous communication between components.

---

## 🛠️ Prerequisites

### 100% Docker Stack

**Minimum version:**
- **Docker Desktop** (Windows/Mac/Linux) with Docker Compose support

All services run in containers: Django, MQTT Worker, Redis, InfluxDB, and Mosquitto.

---

## 🚀 Quick Start with Docker

The fastest way to run the full project is to bring up the entire stack in Docker:

```powershell
# 1. Make sure you are in the project folder
cd path/to/radar_project

# 2. Start all services in the background
docker compose up --build -d

# 3. Follow the web and worker logs if you want to monitor startup
docker compose logs -f web worker
```

**Service URLs:**
- Django (Web Server): http://127.0.0.1:8000/
- InfluxDB (Admin): http://127.0.0.1:8086/ (user: `admin`)
- Redis: localhost:6379
- Mosquitto MQTT: localhost:1883

**Accessing from another device on the same network:**
- Do not use `localhost` on a phone. Open the project using the computer's local IP, e.g. `http://192.168.1.10:8000/`.
- If the browser does not respond, confirm that port `8000` is allowed through the Windows firewall.
- The Django container is already listening on `0.0.0.0:8000` and `DJANGO_ALLOWED_HOSTS` is open for local development.

**To stop all services:**
```powershell
docker compose down
```

**Useful commands:**
```powershell
# Run a manual migration inside the container
docker compose exec web python manage.py migrate

# Create a Django superuser
docker compose exec web python manage.py createsuperuser

# Follow the MQTT worker logs
docker compose logs -f worker
```

---

## 🔧 Environment Variables (.env)

All sensitive credentials and configuration are managed via `.env`. Make sure the file exists at the project root:

```bash
# ============================================
# InfluxDB Configuration
# ============================================
INFLUXDB_URL=http://localhost:8086
INFLUXDB_INIT_USERNAME=admin                       # Initial InfluxDB admin user
INFLUXDB_INIT_PASSWORD=change-me                   # ⚠️ CHANGE IN PRODUCTION
INFLUXDB_TOKEN=change-me-to-a-long-random-token    # ⚠️ GENERATE A NEW TOKEN IN PRODUCTION
INFLUXDB_ORG=radar_project                         # Default organisation
INFLUXDB_BUCKET=sensors_data                       # Bucket for sensor data

# ============================================
# Redis Configuration
# ============================================
REDIS_URL=redis://127.0.0.1:6379/1                 # Redis connection URL

# ============================================
# Django Configuration
# ============================================
DEBUG=True                                         # ⚠️ Set to False in production
SECRET_KEY=your-secret-key-change-in-production    # ⚠️ GENERATE A NEW KEY IN PRODUCTION
```

**⚠️ SECURITY WARNING:**
The placeholder values above are for **local development only**. In production:
- Generate a new `INFLUXDB_TOKEN` via the InfluxDB UI
- Set `INFLUXDB_INIT_PASSWORD` to a strong password
- Generate a new Django `SECRET_KEY`
- Set `DEBUG=False`

---

## 🔧 Environment Variables

The project uses a `.env` file at the root. You can start by copying the example:

```powershell
Copy-Item .env.example .env
```

If you want to change the stack configuration, adjust in particular:
- `INFLUXDB_INIT_USERNAME`
- `INFLUXDB_INIT_PASSWORD`
- `INFLUXDB_ORG`
- `INFLUXDB_BUCKET`
- `INFLUXDB_TOKEN`
- `SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`

The MQTT worker and Django already point to Docker service names:
- Redis: `redis`
- InfluxDB: `influxdb`
- Mosquitto: `mosquitto`

---

## 📊 Data Flow and Architecture

### Flow Diagram

```
┌─────────────────┐
│  Physical Radars│ (Hardware)
│  (Occupancy)    │
└────────┬────────┘
         │
         │ MQTT Publish (batch)
         │ Topic: radar/<SN>/raw
         ▼
┌─────────────────┐
│  MQTT Broker    │ (localhost:1883)
│  (Mosquitto)    │
└────────┬────────┘
         │
         │ Subscribe + Process
         ▼
┌──────────────────────┐
│  Django MQTT Worker  │ (manage.py mqtt_worker)
│  - Auto-discovery    │
│  - State management  │
│  - Data preparation  │
└────────┬────────┬────┘
         │        │
         │        │ Broadcast via channels
         │        │ Group: room_{id}
         │        ▼
         │    ┌──────────────┐
         │    │  WebSocket   │
         │    │  (Real-time) │
         │    └──────────────┘
         │
         │ Write (batch)
         ▼
┌───────────────────┐
│  InfluxDB Time-   │
│  Series (8086)    │
│                   │
│ Measurement:      │
│ - radar_data      │
│                   │
│ Tags:             │
│ - room_id         │
│ - home_id         │
│ - radar_sn        │
│ - target_id       │
│                   │
│ Fields:           │
│ - x (float)       │
│ - y (float)       │
│ - z (float)       │
└───────────────────┘
```

### MQTT Topic and Payload

**Subscription topic:**
```
radar/+/raw
```
Expanded example: `radar/ABC123XYZ/raw` (radar serial number extracted automatically)

**Payload format (JSON):**
```json
[
  {
    "metadata": {
      "server_timestamp": "2026-05-04T14:30:45.123456"
    },
    "data": {
      "targets": [
        {
          "target_id": 1,
          "position": {"x": 2.5, "y": 1.8, "z": 0.95}
        },
        {
          "target_id": 2,
          "position": {"x": 3.1, "y": 2.2, "z": 1.10}
        }
      ],
      "raw_point_cloud": [[2.5, 1.8, 0.95], [2.6, 1.7, 0.96], ...]
    }
  }
]
```

### InfluxDB Schema

**Measurement:** `radar_data`

**Tags** (for filtering and queries):
- `room_id` — Room identifier
- `home_id` — Home identifier
- `radar_sn` — Radar serial number
- `target_id` — Target ID within the frame

**Fields** (numerical data):
- `x` (float) — X coordinate in metres
- `y` (float) — Y coordinate in metres
- `z` (float) — Z coordinate in metres

**Example InfluxQL query:**
```sql
SELECT x, y, z FROM radar_data 
WHERE room_id='5' AND time > now() - 1h
ORDER BY time DESC
```

### Redis Components

Django Channels uses Redis for asynchronous communication between the MQTT Worker and WebSocket connections:

**Channel Groups:**
- `available_radars` — Broadcasting of newly discovered radars
- `room_{id}` — Real-time data broadcasting for each room

Worker broadcast example:
```python
async_to_sync(self.channel_layer.group_send)(
    f'room_{radar.room.id}',
    {
        'type': 'radar_message',
        'data': {
            'targets': radar_data.get("targets", []),
            'radar_sn': serial_number,
            'timestamp': now.strftime('%H:%M:%S')
        }
    }
)
```

---

## 🏗️ App Structure

```text
apps/
├── core/
├── users/
├── environments/
├── sensors_devices/
├── sensors_data/
├── deployment/
├── dashboard/
├── developer/
└── web_api/
```

- **core/**  
   Code shared across all apps. Includes base models with timestamps, mixins, generic permissions, and common utilities.

- **users/**  
   User authentication and profiles: registration, login, logout, and account management. Defines user types (installation technician, resident, carer, and developer) and includes GDPR consent.

- **environments/**  
   Represents the monitored physical space. Stores homes (`Home`) and rooms (`Room`) with name, type, and dimensions.

- **sensors_devices/**  
   Management of physical radar devices: UID/MAC, role (master/worker), status (online/offline), and association to a `Room`.

- **sensors_data/**  
   Processes what the sensors produce: receives point clouds, stores time series, and computes activity metrics (distance travelled, average speed, etc.).

- **deployment/**  
   Installation and calibration workflow. Guides the technician through the wizard (IR1), performs radar auto-discovery (FR1), and supports semi-automatic spatial calibration (FR2).

- **dashboard/**  
   End-user visualisation: per-room heatmaps (FR3), daily/weekly activity charts (FR4/FR8), and movement summary (FR5). Does not persist data — consumes from `sensors_data`.

- **developer/**  
   Technical investigation mode. Allows starting/stopping synchronised raw data acquisition sessions across multiple radars (FR6/IR3) and exporting datasets for offline analysis.

- **web_api/**  
   REST interface for external integration (phones/tablets). Exposes activity data and heatmaps (IR4) as the system's data output point.

*Developed in a Pair-Programming environment.*
