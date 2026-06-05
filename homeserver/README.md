# Radar Project (PECI M3)

Este projeto foi desenvolvido em Django e tem como principal objetivo permitir o registo dinâmico, descoberta (Auto-Discovery) e a monitorização em tempo real de radares de ocupação através de *WebSockets* e *MQTT*.

A arquitetura inclui um **Frontend** interativo impulsionado com HTMX, um **Servidor Django** com suporte para WebSockets (Django Channels), um **Worker MQTT** que ingere dados teleméricos dos radares, uma **Base de Dados Time-Series (InfluxDB)** para persistência histórica de telemetria, e um **Cache em Tempo Real (Redis)** para comunicação assíncrona entre componentes.

---

## 🛠️ Pré-requisitos

### Stack 100% Docker

**Versão mínima:**
- **Docker Desktop** (Windows/Mac/Linux) com suporte para Docker Compose

Todos os serviços passam a correr em containers: Django, Worker MQTT, Redis, InfluxDB e Mosquitto.

---

## 🚀 Quick Start com Docker

A forma mais rápida de correr o projeto completo é subir a stack inteira em Docker:

```powershell
# 1. Certifica-te que estás na pasta do projeto
cd path/to/radar_project

# 2. Sobe todos os serviços em background
docker compose up --build -d

# 3. Verifica os logs do web e do worker se quiseres acompanhar o arranque
docker compose logs -f web worker
```

**Status dos Serviços:**
- Django (Web Server): http://127.0.0.1:8000/
- InfluxDB (Admin): http://127.0.0.1:8086/ (user: `admin`)
- Redis: localhost:6379
- Mosquitto MQTT: localhost:1883

**Acesso a partir de outro dispositivo na mesma rede:**
- Não uses `localhost` no telemóvel. Abre o projeto com o IP local do computador, por exemplo `http://192.168.1.10:8000/`.
- Se o browser não responder, confirma que a porta `8000` está permitida na firewall do Windows.
- O container Django já está a escutar em `0.0.0.0:8000` e `DJANGO_ALLOWED_HOSTS` está aberto para desenvolvimento local.

**Para parar todos os serviços:**
```powershell
docker compose down
```

**Comandos úteis:**
```powershell
# Executar uma migration manual dentro do container
docker compose exec web python manage.py migrate

# Criar superutilizador Django
docker compose exec web python manage.py createsuperuser

# Ver os logs do worker MQTT
docker compose logs -f worker
```

---

## 🔧 Variáveis de Ambiente (.env)

Todas as credenciais e configurações sensíveis são geridas via `.env`. Certifica-te de que o ficheiro existe no root do projeto:

```bash
# ============================================
# InfluxDB Configuration
# ============================================
INFLUXDB_URL=http://localhost:8086
INFLUXDB_INIT_USERNAME=admin                       # Utilizador inicial do InfluxDB
INFLUXDB_INIT_PASSWORD=password_estudante_123      # ⚠️ ALTERAR EM PRODUÇÃO
INFLUXDB_TOKEN=my-super-secret-token               # ⚠️ GERAR TOKEN NOVO EM PRODUÇÃO
INFLUXDB_ORG=radar_project                         # Organização padrão
INFLUXDB_BUCKET=sensors_data                       # Bucket para dados dos sensores

# ============================================
# Redis Configuration
# ============================================
REDIS_URL=redis://127.0.0.1:6379/1                 # URL de conexão do Redis

# ============================================
# Django Configuration
# ============================================
DEBUG=True                                         # ⚠️ Colocar False em produção
SECRET_KEY=your-secret-key-change-in-production  # ⚠️ GERAR NOVA EM PRODUÇÃO
```

**⚠️ AVISO DE SEGURANÇA:**
Os valores padrão acima são apenas para **desenvolvimento local**. Em produção:
- Gera um novo `INFLUXDB_TOKEN` via interface do InfluxDB
- Altera `INFLUXDB_INIT_PASSWORD` para uma senha forte
- Gera um novo `SECRET_KEY` Django
- Define `DEBUG=False`

---

## 🔧 Variáveis de Ambiente

O projeto usa o ficheiro `.env` no root. Podes começar copiando o exemplo:

```powershell
Copy-Item .env.example .env
```

Se quiseres alterar a configuração do stack, ajusta sobretudo:
- `INFLUXDB_INIT_USERNAME`
- `INFLUXDB_INIT_PASSWORD`
- `INFLUXDB_ORG`
- `INFLUXDB_BUCKET`
- `INFLUXDB_TOKEN`
- `SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`

O worker MQTT e o Django já apontam para os nomes de serviço do Docker:
- Redis: `redis`
- InfluxDB: `influxdb`
- Mosquitto: `mosquitto`

---

## 📊 Fluxo de Dados e Arquitetura

### Diagrama de Fluxo

```
┌─────────────────┐
│  Radares Físicos│ (Hardware)
│   (Ocupação)    │
└────────┬────────┘
         │
         │ MQTT Publish (batch)
         │ Topic: radar/<SN>/raw
         ▼
┌─────────────────┐
│  Broker MQTT    │ (localhost:1883)
│  (Mosquitto)    │
└────────┬────────┘
         │
         │ Subscribe + Process
         ▼
┌──────────────────────┐
│  Worker MQTT Django  │ (manage.py mqtt_worker)
│  - Auto-discovery    │
│  - Gerenciar estado  │
│  - Preparar dados    │
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

### Tópico MQTT e Payload

**Tópico de Subscrição:**
```
radar/+/raw
```
Exemplo expandido: `radar/ABC123XYZ/raw` (SN do radar extraído automaticamente)

**Formato do Payload (JSON):**
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

### Schema InfluxDB

**Measurement:** `radar_data`

**Tags** (para filtros e queries):
- `room_id` — Identificador da sala
- `home_id` — Identificador da habitação
- `radar_sn` — Serial Number do radar
- `target_id` — ID do target dentro do frame

**Fields** (dados numéricos):
- `x` (float) — Coordenada X em metros
- `y` (float) — Coordenada Y em metros
- `z` (float) — Coordenada Z em metros

**Exemplar Query InfluxQL:**
```sql
SELECT x, y, z FROM radar_data 
WHERE room_id='5' AND time > now() - 1h
ORDER BY time DESC
```

### Componentes Redis

O Django Channels usa Redis para comunicação assíncrona entre o Worker MQTT e as WebSocket connections:

**Channel Groups:**
- `available_radars` — Broadcasting de descoberta de novos radares
- `room_{id}` — Broadcasting de dados em tempo real para cada sala

Exemplo de broadcast do Worker:
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

## 🏗️ Estrutura Resumida

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
   Código partilhado por todas as apps. Inclui modelos base com timestamps, mixins, permissões genéricas e utilitários comuns.

- **users/**  
   Autenticação e perfis de utilizador: registo, login, logout e gestão de contas. Define tipos de utilizador (técnico de instalação, residente, cuidador e developer) e inclui consentimento RGPD.

- **environments/**  
   Representa o espaço físico monitorizado. Guarda habitações (`Home`) e divisões (`Room`) com nome, tipo e dimensões.

- **sensors_devices/**  
   Gestão dos dispositivos físicos de radar: UID/MAC, papel (master/worker), estado (online/offline) e associação a `Room`.

- **sensors_data/**  
   Processa o que os sensores produzem: recebe point clouds, guarda séries temporais e calcula métricas de atividade (distância percorrida, velocidade média, etc.).

- **deployment/**  
   Processo de instalação e calibração. Guia o técnico no wizard (IR1), faz auto-discovery de radares (FR1) e suporta calibração espacial semi-automática (FR2).

- **dashboard/**  
   Visualização para o utilizador final: heatmaps por divisão (FR3), gráficos de atividade diária/semanal (FR4/FR8) e resumo de movimento (FR5). Não persiste dados, consome de `sensors_data`.

- **developer/**  
   Modo de investigação técnica. Permite iniciar/parar sessões de aquisição sincronizada de dados brutos de múltiplos radares (FR6/IR3) e exportar datasets para análise offline.

- **web_api/**  
   Interface REST para integração externa (telemóveis/tablets). Expõe dados de atividade e heatmaps (IR4), sendo o ponto de saída de dados do sistema.

*Desenvolvido em ambiente de Pair-Programming.*
