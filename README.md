# Game Server Platform (GSP) - Sidecar Architecture

A complete Game Server Provider (GSP) backend using a "Sidecar Proxy" architecture with FastAPI, Docker, and SQLModel.

## Architecture Overview

Every logical "Game Server" consists of **two** Docker containers and one private Docker network:

1. **Proxy Container (Sidecar):** Always-on, minimal resource container that binds to the public port and manages traffic
2. **Game Container (Target):** Heavy resource container running the actual game, started on-demand

### Proxy Logic

- When Game is **OFF**: Traffic triggers a "Wake" webhook to the backend. For TCP, the proxy holds the connection open while starting the game.
- When Game is **ON**: Bidirectional byte streaming between client and game container.

## Project Structure

```
gassorp/
├── main.py                      # FastAPI application entry point
├── models.py                    # SQLModel database models
├── database.py                  # Database configuration
├── requirements.txt             # Python dependencies
├── proxy_service/              # Sidecar proxy service
│   ├── Dockerfile
│   └── main.py                 # Async proxy logic
├── services/
│   ├── docker_manager.py       # SidecarManager for container orchestration
│   ├── lifecycle.py            # Background task manager (idle check, billing)
│   └── auth.py                 # Authentication stubs
├── routers/
│   ├── auth.py                 # Authentication routes
│   ├── dashboard.py            # Server management routes
│   └── webhooks.py             # Internal webhooks
├── templates/                  # Jinja2 templates
│   ├── login.html
│   ├── dashboard.html
│   ├── server_detail.html
│   ├── create_server.html
│   └── billing.html
└── tests/                      # Test suite with mocked Docker
```

## Features

- **Server-Side Rendering:** Jinja2 templates (no frontend frameworks)
- **Mock OAuth:** Stub Google/Microsoft authentication for development
- **Auto-Sleep:** Servers hibernate when idle (15 min low CPU threshold)
- **Hourly Billing:** Automatic credit deduction while servers are running
- **Cloud Backups:** Export server data to Google Cloud Storage
- **Real-time Logs:** View game container logs in the dashboard
- **Resource Monitoring:** CPU and memory usage tracking

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

3. **Start the application:**
```bash
python main.py
```

The server will be available at `http://localhost:8000`

## API Endpoints

### Authentication
- `GET /auth/login` - Login page
- `POST /auth/mock-login` - Mock OAuth login
- `GET /auth/mock/{provider}` - Mock OAuth callback
- `GET /auth/logout` - Logout

### Dashboard
- `GET /dashboard` - Server list
- `GET /servers/create` - Create server form
- `POST /servers/create` - Create new server
- `GET /servers/{id}` - Server detail page
- `POST /servers/{id}/wake` - Start server
- `POST /servers/{id}/hibernate` - Stop server
- `POST /servers/{id}/backup` - Backup to cloud
- `POST /servers/{id}/delete` - Delete server
- `GET /servers/{id}/logs` - Server logs (AJAX)

### Billing
- `GET /billing` - Billing page
- `POST /billing/add-funds` - Add credits (mock)

### Webhooks (Internal)
- `POST /api/webhook/wake` - Proxy wake trigger

## Database Models

- **User:** id, email, provider, credits, is_admin
- **GameImage:** id, friendly_name, docker_image, default_internal_port, min_ram, min_cpu
- **Server:** id, user_id, game_image_id, container_ids, ports, state (RUNNING/SLEEPING/STARTING/STOPPING)
- **Transaction:** id, user_id, amount, type (DEPOSIT/HOURLY_CHARGE)

## Supported Games

Default game images included:
- Minecraft Java (TCP, port 25565)
- Valheim (UDP, port 2456)
- Satisfactory (UDP, port 7777)

## Testing

Run the test suite with mocked Docker:

```bash
pytest tests/ -v
```

## Requirements

- Python 3.11+
- Docker (running and accessible from Python)
- Google Cloud Storage (for backups, optional)
