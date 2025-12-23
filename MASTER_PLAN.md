# 🚀 GSP: Game Server Platform - Master Implementation Plan

**Objective:** Build a fully automated Game Server Platform with credit-based billing, robust Google/Microsoft authentication, and plug-and-play support for Minecraft, Terraria, and Factorio. 

**Constraint:** No local password handling. Pure OAuth. 

**Infrastructure:** Docker (Local for now, abstracted for AWS later).

---

## 🛠 Phase 1: Authentication & User Model Refactor

**Goal:** Replace mock auth with real OAuth libraries and update the User model to support credits and provider IDs.

### 1.1 Update Dependencies

Add `fastapi-sso` to requirements.txt. This library handles the heavy lifting for Google and Microsoft auth.

### 1.2 Database Schema Update (models.py)

Refactor the User model to remove passwords and add provider tracking.

```python
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    display_name: str
    
    # Auth Fields
    provider: str = Field(index=True) # "google", "microsoft", "dev"
    provider_id: str = Field(index=True) # The unique ID from the provider
    avatar_url: Optional[str] = None
    
    # Billing Fields
    credits: float = Field(default=10.0) # Give 10 free credits on sign up
    is_admin: bool = Field(default=False)
```

### 1.3 Implement OAuth Routes (routers/auth.py)

Replace the current logic with fastapi-sso.

**Requirements:**

- **Imports:** `from fastapi_sso.sso.google import GoogleSSO`, `from fastapi_sso.sso.microsoft import MicrosoftSSO`
- **Config:** Read `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, etc., from `.env`.
- **Endpoints:**
  - `GET /auth/login/google` -> Triggers redirect.
  - `GET /auth/callback/google` -> Processes return, finds/creates user in DB, sets Session Cookie.
  - `GET /auth/login/microsoft` -> Triggers redirect.
  - `GET /auth/callback/microsoft` -> Processes return.
  - **Keep:** `POST /auth/dev-login` for local testing (Create a user `admin@gsp.dev` with 1000 credits).

**Instruction for Agent:** Ensure that if a user logs in with an email that already exists, we update their avatar/name. If new, create them with default credits.

---

## 🏗 Phase 2: The Core Plugin Engine

**Goal:** Connect the file-based games/ folder to the DockerManager. The system must read a config.json and know how to start that specific container.

### 2.1 Standardize config.json

Define the schema that every game folder MUST have.

```json
{
  "meta": {
    "id": "terraria",
    "name": "Terraria",
    "version": "1.4.4"
  },
  "docker": {
    "image": "raysan5/tshock",
    "tag": "latest",
    "ports": {
      "7777/tcp": "auto" 
    },
    "environment": {
      "T_WORLD": "/root/.local/share/Terraria/Worlds/world.wld",
      "T_MOTD": "Welcome to GSP Terraria"
    },
    "volumes": {
      "/root/.local/share/Terraria/Worlds": "data"
    }
  },
  "resources": {
    "cpu": 1.0,
    "memory": "1G"
  }
}
```

### 2.2 Update PluginLoader (core/plugin_loader.py)

- Implement `load_all_plugins()`: Scan games/ directory.
- Validate that every folder has a `config.json` and a `logo.png`.
- Return a list of available games to be displayed on the "Create Server" page.

### 2.3 Refactor DockerManager (services/docker_manager.py)

Currently, it likely hardcodes Minecraft logic. Refactor `deploy_server` to accept a GameConfig.

**Logic:**

1. **Pull Image:** `client.images.pull(config['docker']['image'])`
2. **Port Mapping:** If config says `"7777/tcp": "auto"`, find a free open port on the host (e.g., 30001) and map it. Save this port to the Server database entry.
3. **Volume Management:** Create a Docker volume named `server_{id}_data`.
4. **Sidecar Integration:** (Critical) The manager must launch the Proxy Container first, binding the public port, and then the Game Container attached to the same network.

---

## 🎮 Phase 3: Game Implementation (The Big Three)

**Goal:** Create the actual configuration and adapter files for the requested games.

### 3.1 Minecraft Java (games/minecraft_java/)

- **Image:** `itzg/minecraft-server`
- **Config:** Port 25565 (TCP). Env vars: `EULA=TRUE`, `TYPE=PAPER`.
- **Adapter:** Use `mcstatus` library for query.

### 3.2 Terraria (games/terraria/)

- **Image:** `raysan5/tshock`
- **Config:** Port 7777 (TCP).
- **Adapter:** Terraria query protocol (TCP).
  - **Note:** Use a simple TCP socket connect test for "Player Count" if a library isn't available, or search for a python TShock query library.

### 3.3 Factorio (games/factorio/)

- **Image:** `factoriotools/factorio`
- **Config:** Port 34197 (UDP).
- **Special Requirement:** Factorio runs as a specific user ID. The DockerManager might need to handle `user: 845` in the container config.
- **Adapter:** Factorio requires an RCON client to get player counts.
  - **Action:** Add `python-rcon` to requirements.

---

## 💰 Phase 4: Billing & Lifecycle Daemon

**Goal:** The system needs a "heartbeat" to charge users and stop servers when they run out of money.

### 4.1 The Billing Tick (services/billing.py)

Create a background service function `process_billing_cycle()`.

**Logic:**

1. Query DB for all `Server` where `state == RUNNING`.
2. For each server:
   - Calculate cost (e.g., 0.1 credits/minute).
   - Deduct from `server.owner.credits`.
   - Check Balance: If credits <= 0:
     - Log: "User ran out of funds."
     - Call `docker_manager.stop_server(server.id)`.
     - Send Webhook/Notification (Optional).
3. Commit DB transaction.

### 4.2 Integration in main.py

Use FastAPI's `on_event("startup")` to launch an asyncio loop that runs `process_billing_cycle()` every 60 seconds.

```python
@app.on_event("startup")
async def start_billing_loop():
    asyncio.create_task(billing_ticker())

async def billing_ticker():
    while True:
        await asyncio.sleep(60)
        await services.billing.process_billing_cycle()
```

---

## 🖥 Phase 5: UI Integration

**Goal:** Connect the backend logic to the Jinja2 templates.

### 5.1 Login Page

- Remove the Email/Password form.
- Add "Login with Google" and "Login with Microsoft" buttons (targeting the new endpoints).
- Keep "Dev Login" button (hidden or subtle).

### 5.2 Create Server Page

- Loop through `PluginLoader.get_plugins()`.
- Generate a card for each game (Minecraft, Terraria, Factorio).
- When clicked, the form submits `game_id` to the backend.

### 5.3 Dashboard

- Display `User.credits` prominently in the header.
- Show the "Public Port" for each server.
- Add a "Status" badge that uses the Game Adapter's `get_player_count` (implemented in previous turns).

---

## 📝 Instructions for the Agent

*(Copy and paste this section into the chat)*

1. **Agent Instructions:**
   - Read MASTER_PLAN.md carefully.
   - Start with Phase 1. Modify models.py and create routers/auth.py using fastapi-sso. Don't worry about the actual Client IDs (use placeholders), but the logic must be sound.
   - Move to Phase 2. Create the games/ directory structure. Write the core/plugin_loader.py.
   - Execute Phase 3. Create the config.json and adapter.py files for Minecraft, Terraria, and Factorio. Ensure the config.json maps the correct Docker Hub images.
   - Execute Phase 4. Write the billing logic. Ensure servers stop when money runs out.
   - Execute Phase 5. Update the HTML templates to reflect these changes.

2. **Verification:** After each phase, run pytest (if tests exist) or verify that the python files compile without syntax errors.
