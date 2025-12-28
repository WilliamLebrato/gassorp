# Quick Start Guide - GSP Development Environment

## Prerequisites
- Docker and Docker Compose installed
- Google OAuth account (optional, for production)
- Microsoft OAuth account (optional, for production)

## Setup Instructions

### 1. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your OAuth credentials (see below)
nano .env
```

### 2. Configure OAuth Providers (Optional for DEV mode)

**For Google OAuth:**
1. Go to: https://console.cloud.google.com/apis/credentials
2. Create a new OAuth 2.0 Client ID (Web application)
3. Add redirect URI: `http://localhost:8000/auth/callback/google`
4. Copy Client ID and Client Secret to your `.env` file

**For Microsoft OAuth:**
1. Go to: https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
2. Click "New registration"
3. Select "Web" platform
4. Add redirect URI: `http://localhost:8000/auth/callback/microsoft`
5. Copy Application (client) ID and generate a client secret
6. Add to your `.env` file

**DEV MODE (No OAuth required):**
- Set `DEV_MODE=true` in `.env`
- Set `VITE_DEV_MODE=true` in frontend `.env`
- The "DEV LOGIN" button will appear on the login page

### 3. Start the Development Environment

```bash
# Start all services with hot-reload
docker-compose -f docker-compose.dev.yml up --build

# Or run in background
docker-compose -f docker-compose.dev.yml up -d --build
```

### 4. Access the Application

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **Swagger API Docs:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc

### 5. Test the Authentication

**Option A: DEV LOGIN (Recommended for testing)**
1. Open http://localhost:5173
2. Click the purple "⚡ DEV LOGIN" button
3. You'll be logged in as admin@gsp.dev with 1000 credits

**Option B: Google OAuth**
1. Click "Continue with Google"
2. Complete Google sign-in flow
3. Account will be created automatically with 10 credits

**Option C: Microsoft OAuth**
1. Click "Continue with Microsoft"
2. Complete Microsoft sign-in flow
3. Account will be created automatically with 10 credits

### 6. Hot Reload Development

- **Backend:** Edit files in `backend/app/`, changes auto-reload
- **Frontend:** Edit files in `frontend/src/`, Vite hot-reloads in browser

### 7. Stop the Environment

```bash
docker-compose -f docker-compose.dev.yml down

# To remove volumes as well
docker-compose -f docker-compose.dev.yml down -v
```

## Port Mapping

| Service | Container Port | Host Port |
|---------|---------------|-----------|
| Backend | 8000 | 8000 |
| Frontend | 5173 | 5173 |

## Environment Variable Reference

### Backend (.env)
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth secret
- `GOOGLE_REDIRECT_URI` - http://localhost:8000/auth/callback/google
- `MICROSOFT_CLIENT_ID` - Microsoft OAuth client ID
- `MICROSOFT_CLIENT_SECRET` - Microsoft OAuth secret
- `MICROSOFT_REDIRECT_URI` - http://localhost:8000/auth/callback/microsoft
- `DEV_MODE` - Enable DEV LOGIN button (true/false)
- `SECRET_KEY` - JWT signing key (generate with: openssl rand -hex 32)

### Frontend (.env)
- `VITE_API_URL` - Backend API URL (http://localhost:8000)
- `VITE_DEV_MODE` - Show DEV LOGIN button (true/false)

## Troubleshooting

**Backend not loading?**
- Check logs: `docker-compose -f docker-compose.dev.yml logs backend`
- Ensure port 8000 is not in use
- Verify `.env` file exists in backend directory

**Frontend not connecting to backend?**
- Check `VITE_API_URL` in frontend `.env`
- Verify CORS settings in backend (main.py)
- Check browser console for errors

**OAuth buttons show error?**
- Verify OAuth credentials are correct
- Check redirect URIs match exactly
- Ensure OAuth app is configured for "Web" platform

**DEV LOGIN button not showing?**
- Set `DEV_MODE=true` in backend `.env`
- Set `VITE_DEV_MODE=true` in frontend `.env`
- Restart containers

## API Testing with Swagger

1. Go to http://localhost:8000/api/docs
2. Click "Authorize" button
3. Login via DEV LOGIN or OAuth to get session cookie
4. Test API endpoints directly in the browser
