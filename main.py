from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import logging
import os
from dotenv import load_dotenv

from database import init_db, engine
from models import GameImage
from services.docker_manager import SidecarManager
from services.lifecycle import LifecycleManager
from routers import auth, dashboard, webhooks

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

docker_manager: SidecarManager = None
lifecycle_manager: LifecycleManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    
    from database import Session
    session = Session()
    
    existing_images = session.exec(GameImage.select()).all()
    if not existing_images:
        default_images = [
            GameImage(
                friendly_name="Minecraft Java",
                docker_image="itzg/minecraft-server:latest",
                default_internal_port=25565,
                min_ram="2g",
                min_cpu="1.0",
                protocol="tcp",
                description="Official Minecraft Java Edition server"
            ),
            GameImage(
                friendly_name="Valheim",
                docker_image="lloesche/valheim-server:latest",
                default_internal_port=2456,
                min_ram="4g",
                min_cpu="2.0",
                protocol="udp",
                description="Valheim dedicated server"
            ),
            GameImage(
                friendly_name="Satisfactory",
                docker_image="wolveix/satisfactory-server:latest",
                default_internal_port=7777,
                min_ram="8g",
                min_cpu="4.0",
                protocol="udp",
                description="Satisfactory dedicated server"
            )
        ]
        for img in default_images:
            session.add(img)
        session.commit()
        logger.info("Added default game images")
    
    session.close()
    
    global docker_manager, lifecycle_manager
    
    webhook_secret = os.getenv("WEBHOOK_SECRET", "default-secret")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    gcs_bucket = os.getenv("GOOGLE_CLOUD_BUCKET", "gsp-backups")
    
    docker_manager = SidecarManager(webhook_secret, backend_url, gcs_bucket)
    lifecycle_manager = LifecycleManager(docker_manager, lambda: Session())
    
    dashboard.set_managers(docker_manager, lifecycle_manager)
    webhooks.set_lifecycle_manager(lifecycle_manager)
    
    await lifecycle_manager.start()
    
    yield
    
    await lifecycle_manager.stop()


app = FastAPI(
    title="Game Server Platform",
    description="Sidecar-based game server orchestrator",
    version="1.0.0",
    lifespan=lifespan
)

templates = Jinja2Templates(directory="templates")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(dashboard.router_main)
app.include_router(webhooks.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
