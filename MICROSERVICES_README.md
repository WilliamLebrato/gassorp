# GSP Microservices Architecture

## Overview

This is a refactored distributed microservices architecture for the Game Server Platform (GSP). The system is split into three independent services:

1. **Frontend**: React-based UI (port 3000)
2. **Backend**: FastAPI for auth, billing, orchestration (port 8000)
3. **Node Agent**: Docker executor for managing game containers (port 8001)

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────▶│   Backend   │────▶│ Node Agent  │
│  (React)    │     │  (FastAPI)  │     │  (FastAPI)  │
│  Port 3000  │     │  Port 8000  │     │  Port 8001  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Database   │
                    │ (SQLite)    │
                    └─────────────┘
```

## Services

### Frontend
- **Technology**: React + Vite
- **Responsibility**: User interface, display logic
- **Port**: 3000
- **Build**: Multi-stage Docker build (Node → Nginx)

### Backend
- **Technology**: Python FastAPI
- **Responsibility**: 
  - User authentication (OAuth)
  - Database management
  - Billing and credits
  - Server orchestration
  - Plugin system
- **Port**: 8000
- **Database**: SQLite (with PostgreSQL option)

### Node Agent
- **Technology**: Python FastAPI
- **Responsibility**:
  - Docker container management
  - Proxy container spawning
  - Server stats monitoring
  - Container logs
- **Port**: 8001
- **Access**: Requires `/var/run/docker.sock` mount

## Quick Start

1. **Copy environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit .env with your OAuth credentials** (optional for testing)

3. **Start all services**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000/docs
   - Node Agent: http://localhost:8001/docs

## Development

### Running services individually:

**Backend**:
```bash
cd backend/app
pip install -r ../../requirements.txt
python main.py
```

**Node Agent**:
```bash
cd node-agent/app
pip install -r ../../requirements.txt
python main.py
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

### Backend (port 8000)
- `POST /auth/login/google` - Google OAuth login
- `POST /auth/login/microsoft` - Microsoft OAuth login
- `GET /api/servers` - List user's servers
- `POST /api/servers` - Create new server
- `GET /api/servers/{id}` - Get server details
- `POST /api/servers/{id}/wake` - Wake hibernating server
- `POST /api/servers/{id}/hibernate` - Hibernate server
- `DELETE /api/servers/{id}` - Delete server
- `GET /api/servers/{id}/logs` - Get server logs

### Node Agent (port 8001)
- `POST /deploy` - Deploy new game server
- `POST /servers/{id}/wake` - Wake server
- `POST /servers/{id}/hibernate` - Hibernate server
- `DELETE /servers/{id}` - Delete server
- `GET /servers/{id}/stats` - Get container stats
- `GET /servers/{id}/logs` - Get container logs

## Communication Flow

### Server Deployment:
1. Frontend sends POST /api/servers to Backend
2. Backend checks credits, validates request
3. Backend sends POST /deploy to Node Agent
4. Node Agent creates Docker containers (game + proxy)
5. Node Agent returns container IDs to Backend
6. Backend saves server metadata to database

### Server Wake:
1. Frontend sends POST /api/servers/{id}/wake to Backend
2. Backend validates user credits
3. Backend sends POST /servers/{id}/wake to Node Agent
4. Node Agent starts the game container
5. Backend updates server state in database

## Security

- **Node Secret**: Shared secret between Backend and Node Agent (X-Node-Secret header)
- **OAuth**: Google/Microsoft SSO for user authentication
- **CORS**: Configured for local development

## Deployment

For production deployment:
1. Use PostgreSQL instead of SQLite
2. Set strong secrets in environment variables
3. Configure proper OAuth redirect URIs
4. Use HTTPS/TLS for all communications
5. Deploy Node Agents on separate physical servers
6. Configure proper firewall rules

## Monitoring

Each service exposes health endpoints:
- Frontend: N/A (serves static files)
- Backend: Check application logs
- Node Agent: GET /health

## Troubleshooting

**Node Agent can't connect to Docker?**
- Ensure `/var/run/docker.sock` is mounted in docker-compose.yml
- Add `privileged: true` to node-agent service

**Backend can't reach Node Agent?**
- Check `NODE_URL` environment variable
- Ensure both services are on the same Docker network

**Frontend can't reach Backend?**
- Check Vite proxy configuration in `vite.config.js`
- Ensure CORS is configured correctly
