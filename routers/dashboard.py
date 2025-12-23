from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from models import User, Server, ServerCreate, GameImage, Transaction
from services.auth import get_current_active_user, oauth2_scheme
from services.docker_manager import SidecarManager
from services.lifecycle import LifecycleManager
from database import get_session
from typing import Optional
import logging

router = APIRouter(prefix="/servers", tags=["servers"])
templates = Jinja2Templates(directory="templates")

docker_mgr: Optional[SidecarManager] = None
lifecycle_mgr: Optional[LifecycleManager] = None
logger = logging.getLogger(__name__)


def set_managers(dmgr: SidecarManager, lmgr: LifecycleManager):
    global docker_mgr, lifecycle_mgr
    docker_mgr = dmgr
    lifecycle_mgr = lmgr


async def require_auth(request: Request, session: Session = Depends(get_session)):
    from services.auth import get_current_user
    from fastapi.security.utils import get_authorization_scheme_param
    
    token = request.cookies.get("access_token")
    if not token:
        logger.warning("No access_token cookie found")
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token, session)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=303,
            detail=f"Authentication failed: {str(e)}",
            headers={"Location": "/auth/login"}
        )


@router.get("/create", summary="Create Server Page", description="Display form to create a new game server.")
async def create_server_page(request: Request, user: User = Depends(require_auth), session: Session = Depends(get_session)):
    game_images = session.exec(select(GameImage)).all()
    return templates.TemplateResponse("create_server.html", {
        "request": request,
        "user": user,
        "game_images": game_images
    })


@router.post("/create", summary="Deploy New Server", description="Provisions a new game server and sidecar proxy. Requires sufficient credits.", response_description="Redirects to server detail page.")
async def create_server(
    request: Request,
    friendly_name: str = Form(...),
    game_image_id: int = Form(...),
    auto_sleep: bool = Form(False),
    session: Session = Depends(get_session),
    user: User = Depends(require_auth)
):
    game_image = session.get(GameImage, game_image_id)
    if not game_image:
        raise HTTPException(status_code=404, detail="Game image not found")
    
    server = Server(
        user_id=user.id,
        game_image_id=game_image_id,
        friendly_name=friendly_name,
        env_vars={},
        auto_sleep=auto_sleep,
        state=ServerState.SLEEPING
    )
    session.add(server)
    session.commit()
    session.refresh(server)
    
    if docker_mgr:
        docker_mgr.deploy(server, game_image)
        session.add(server)
        session.commit()
    
    return RedirectResponse(url=f"/servers/{server.id}", status_code=303)


from models import ServerState


@router.get("/{server_id}", summary="Server Detail", description="View server details, stats, and controls.")
async def server_detail(
    server_id: int,
    request: Request,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    stats = docker_mgr.get_container_stats(server) if docker_mgr else {}
    public_ip = request.headers.get("X-Forwarded-For", "localhost")
    
    return templates.TemplateResponse("server_detail.html", {
        "request": request,
        "server": server,
        "stats": stats,
        "public_ip": public_ip,
        "user": user
    })


@router.get("/{server_id}/logs", summary="Server Logs", description="Retrieve container logs for the game server.")
async def server_logs(
    server_id: int,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    logs = docker_mgr.get_container_logs(server) if docker_mgr else "No logs available"
    return logs


@router.post("/{server_id}/wake", summary="Wake Server", description="Start a hibernating server. Requires credits.")
async def wake_server(
    server_id: int,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if docker_mgr and user.credits > 0:
        docker_mgr.wake(server)
        server.state = ServerState.RUNNING
        session.add(server)
        session.commit()
    
    return RedirectResponse(url=f"/servers/{server_id}", status_code=303)


@router.post("/{server_id}/hibernate", summary="Hibernate Server", description="Stop a running server and save state.")
async def hibernate_server(
    server_id: int,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if docker_mgr:
        docker_mgr.hibernate(server)
        server.state = ServerState.SLEEPING
        session.add(server)
        session.commit()
    
    return RedirectResponse(url=f"/servers/{server_id}", status_code=303)


@router.post("/{server_id}/backup", summary="Backup Server", description="Export server data to GCS backup.")
async def backup_server(
    server_id: int,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if docker_mgr:
        backup_path = docker_mgr.export_data(server)
        if backup_path:
            server.gcs_backup_path = backup_path
            session.add(server)
            session.commit()
    
    return RedirectResponse(url=f"/servers/{server_id}", status_code=303)


@router.post("/{server_id}/delete", summary="Delete Server", description="Permanently delete a server and its containers.")
async def delete_server(
    server_id: int,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if docker_mgr:
        docker_mgr.delete(server)
    
    session.delete(server)
    session.commit()
    
    return RedirectResponse(url="/dashboard", status_code=303)


from fastapi import APIRouter

router_main = APIRouter()


@router_main.get("/dashboard")
async def dashboard(
    request: Request,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session)
):
    servers = session.exec(
        select(Server).where(Server.user_id == user.id)
    ).all()
    
    for server in servers:
        session.refresh(server)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "servers": servers
    })


@router_main.get("/billing")
async def billing_page(
    request: Request,
    user: User = Depends(require_auth),
    session: Session = Depends(get_session)
):
    transactions = session.exec(
        select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.timestamp.desc())
    ).all()
    
    return templates.TemplateResponse("billing.html", {
        "request": request,
        "user": user,
        "transactions": transactions
    })


@router_main.post("/billing/add-funds")
async def add_funds(
    user: User = Depends(require_auth),
    session: Session = Depends(get_session)
):
    if lifecycle_mgr:
        await lifecycle_mgr.add_credits(user.id, 10.0, "Mock deposit")
    
    return RedirectResponse(url="/billing", status_code=303)


@router_main.get("/")
async def index():
    return RedirectResponse(url="/dashboard")
