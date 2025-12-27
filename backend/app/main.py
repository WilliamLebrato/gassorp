from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, engine, get_session
from models import GameImage, Server, User, Transaction
from sqlmodel import select

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

lifecycle_manager = None
plugin_loader = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    
    session_gen = get_session()
    session = next(session_gen)
    
    existing_images = session.exec(select(GameImage)).all()
    if not existing_images:
        logger.info("Adding default game images")
        default_images = [
            GameImage(
                friendly_name="Minecraft Java",
                docker_image="itzg/minecraft-server:latest",
                default_internal_port=25565,
                min_ram="1G",
                min_cpu="0.5",
                protocol="tcp",
                description="Official Minecraft Java Edition server with support for multiple versions and modpacks."
            ),
            GameImage(
                friendly_name="Valheim",
                docker_image="lloesche/valheim-server:latest",
                default_internal_port=2456,
                min_ram="2G",
                min_cpu="1.0",
                protocol="udp",
                description="Valheim dedicated server"
            )
        ]
        for img in default_images:
            session.add(img)
        session.commit()
        logger.info("Added default game images")
    
    session.close()
    
    global lifecycle_manager, plugin_loader
    
    try:
        from services.lifecycle import LifecycleManager
        from services.node_client import NodeClient
        
        node_url = os.getenv("NODE_URL", "http://node-agent:8001")
        node_secret = os.getenv("NODE_SECRET", "dev_secret")
        node_client = NodeClient(node_url, node_secret)
        
        lifecycle_manager = LifecycleManager(node_client, lambda: next(get_session()))
        await lifecycle_manager.start()
        
        from routers import api_servers
        api_servers.set_node_client(node_client)
        
        logger.info("Lifecycle manager started")
    except Exception as e:
        logger.warning(f"Could not initialize lifecycle manager: {e}")
        lifecycle_manager = None
    
    try:
        from core.plugin_loader import PluginLoader
        plugin_loader = PluginLoader(games_dir="games")
        plugin_loader._load_plugins_sync()
        logger.info(f"Loaded {len(plugin_loader.get_all_plugins())} game plugins")
    except Exception as e:
        logger.error(f"Failed to load plugins: {e}")
        plugin_loader = None
    
    try:
        from services.billing import billing_daemon
        import asyncio
        asyncio.create_task(billing_daemon(lambda: next(get_session())))
        logger.info("Billing daemon started")
    except Exception as e:
        logger.error(f"Failed to start billing daemon: {e}")
    
    yield
    
    if lifecycle_manager:
        await lifecycle_manager.stop()


app = FastAPI(
    title="GSP Backend API",
    description="API for managing Game Server Platform - handles auth, billing, and orchestration",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import auth, dashboard, webhooks, admin, api_servers

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(dashboard.router_main)
app.include_router(webhooks.router)
app.include_router(admin.router)
app.include_router(api_servers.router)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error": str(exc.detail)}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
            "type": type(exc).__name__
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
