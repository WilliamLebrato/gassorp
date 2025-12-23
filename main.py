from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
import logging
import os
from dotenv import load_dotenv

from database import init_db, engine
from models import GameImage
from services.docker_manager import SidecarManager
from services.lifecycle import LifecycleManager
from routers import auth, dashboard, webhooks, admin
from core.plugin_loader import PluginLoader

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

docker_manager: SidecarManager = None
lifecycle_manager: LifecycleManager = None
plugin_loader: PluginLoader = None

# Initialize SSO providers
try:
    from fastapi_sso.sso.google import GoogleSSO
    from fastapi_sso.sso.microsoft import MicrosoftSSO
    
    google_sso = GoogleSSO(
        client_id=os.getenv("GOOGLE_CLIENT_ID", "placeholder-id"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "placeholder-secret"),
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback/google"),
        allow_insecure_http=True,
        use_state=True
    )
    
    microsoft_sso = MicrosoftSSO(
        client_id=os.getenv("MICROSOFT_CLIENT_ID", "placeholder-id"),
        client_secret=os.getenv("MICROSOFT_CLIENT_SECRET", "placeholder-secret"),
        redirect_uri=os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/auth/callback/microsoft"),
        allow_insecure_http=True,
        use_state=True
    )
    
    auth.set_sso_providers(google_sso, microsoft_sso)
    logger.info("OAuth providers initialized")
except ImportError:
    logger.warning("fastapi-sso not installed, OAuth will not be available")
except Exception as e:
    logger.error(f"Failed to initialize OAuth providers: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    
    from database import get_session
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
    
    try:
        docker_manager = SidecarManager(webhook_secret, backend_url, gcs_bucket)
        lifecycle_manager = LifecycleManager(docker_manager, lambda: next(get_session()))
        
        from services.game_query import GameQueryService
        game_query_service = GameQueryService()
        
        dashboard.set_managers(docker_manager, lifecycle_manager, game_query_service)
        webhooks.set_lifecycle_manager(lifecycle_manager)
        
        await lifecycle_manager.start()
    except Exception as e:
        logger.warning(f"Could not initialize Docker manager: {e}")
        docker_manager = None
        lifecycle_manager = None
    
    try:
        from core.plugin_loader import PluginLoader
        global plugin_loader
        plugin_loader = PluginLoader(games_dir="games")
        plugin_loader._load_plugins_sync()
        admin.set_plugin_loader(plugin_loader)
        logger.info(f"Loaded {len(plugin_loader.get_all_plugins())} game plugins")
    except Exception as e:
        logger.error(f"Failed to load plugins: {e}")
        plugin_loader = None
    
    # Start billing daemon
    try:
        from services.billing import billing_daemon
        asyncio.create_task(billing_daemon())
        logger.info("Billing daemon started")
    except Exception as e:
        logger.error(f"Failed to start billing daemon: {e}")
    
    yield
    
    if lifecycle_manager:
        await lifecycle_manager.stop()


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="GSP API",
        version="1.0.0",
        description="API for managing Game Server Platform instances, billing, and lifecycle.",
        routes=app.routes,
        contact={
            "name": "GSP Dev Team",
            "email": "admin@gsp.dev"
        }
    )
    
    openapi_schema["components"]["securitySchemes"] = {
        "cookieAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "access_token",
            "description": "JWT token stored in HttpOnly cookie for authentication"
        }
    }
    
    for path in openapi_schema["paths"].values():
        for operation in path.values():
            if "security" not in operation or operation["security"] is None:
                operation["security"] = [{"cookieAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app = FastAPI(
    title="GSP API",
    description="API for managing Game Server Platform instances, billing, and lifecycle.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.openapi = custom_openapi


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303 and "Location" in exc.headers:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=exc.headers["Location"], status_code=303)
    
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error": str(exc.detail)}
    )


templates = Jinja2Templates(directory="templates")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(dashboard.router_main)
app.include_router(webhooks.router)
app.include_router(admin.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    from fastapi.responses import JSONResponse
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
    import os
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
