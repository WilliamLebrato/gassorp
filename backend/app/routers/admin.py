from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from models import User, GameImage
from services.auth import require_admin
from database import get_session
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")

plugin_loader = None


def set_plugin_loader(loader):
    global plugin_loader
    plugin_loader = loader


async def require_auth_admin(request: Request, session: Session = Depends(get_session)):
    from services.auth import get_current_user
    
    token = request.cookies.get("access_token")
    if not token:
        logger.warning("No access_token cookie found")
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token, session)
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
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


@router.get("/plugins", summary="Plugin Dashboard", description="View all loaded game plugins and their status (Admin only)")
async def list_plugins(
    request: Request,
    user: User = Depends(require_auth_admin),
    session: Session = Depends(get_session)
):
    if not plugin_loader:
        raise HTTPException(status_code=503, detail="Plugin system not initialized")
    
    plugins = plugin_loader.get_all_plugins()
    return templates.TemplateResponse("admin/plugins.html", {
        "request": request,
        "user": user,
        "plugins": plugins
    })


@router.post("/plugins/{plugin_id}/reload", summary="Reload Plugin", description="Reload a specific plugin (Admin only)")
async def reload_plugin(
    plugin_id: str,
    user: User = Depends(require_auth_admin),
    session: Session = Depends(get_session)
):
    if not plugin_loader:
        raise HTTPException(status_code=503, detail="Plugin system not initialized")
    
    plugin = plugin_loader.reload_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    
    return RedirectResponse(url="/admin/plugins", status_code=303)


@router.get("/games", summary="List Games", description="View all game images in the catalog (Admin only)")
async def list_games(
    request: Request,
    user: User = Depends(require_auth_admin),
    session: Session = Depends(get_session)
):
    games = session.exec(select(GameImage)).all()
    return templates.TemplateResponse("admin/games.html", {
        "request": request,
        "user": user,
        "games": games
    })


@router.get("/games/new", summary="New Game Form", description="Display form to add a new game image (Admin only)")
async def new_game_form(
    request: Request,
    user: User = Depends(require_auth_admin),
    session: Session = Depends(get_session)
):
    return templates.TemplateResponse("admin/game_form.html", {
        "request": request,
        "user": user,
        "game": None
    })


@router.post("/games", summary="Create Game", description="Add a new game image to the catalog (Admin only)")
async def create_game(
    request: Request,
    friendly_name: str = Form(...),
    docker_image: str = Form(...),
    default_internal_port: int = Form(...),
    min_ram: str = Form(...),
    min_cpu: str = Form(...),
    protocol: str = Form("tcp"),
    description: Optional[str] = Form(None),
    icon_url: str = Form("/static/img/default_icon.png"),
    wallpaper_url: str = Form("/static/img/default_wallpaper.jpg"),
    user: User = Depends(require_auth_admin),
    session: Session = Depends(get_session)
):
    existing = session.exec(
        select(GameImage).where(GameImage.friendly_name == friendly_name)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Game with this name already exists")
    
    game = GameImage(
        friendly_name=friendly_name,
        docker_image=docker_image,
        default_internal_port=default_internal_port,
        min_ram=min_ram,
        min_cpu=min_cpu,
        protocol=protocol,
        description=description,
        icon_url=icon_url,
        wallpaper_url=wallpaper_url
    )
    
    session.add(game)
    session.commit()
    session.refresh(game)
    
    logger.info(f"Created new game image: {friendly_name} by {user.email}")
    
    return RedirectResponse(url="/admin/games", status_code=303)


@router.get("/games/{game_id}/edit", summary="Edit Game Form", description="Display form to edit a game image (Admin only)")
async def edit_game_form(
    game_id: int,
    request: Request,
    user: User = Depends(require_auth_admin),
    session: Session = Depends(get_session)
):
    game = session.get(GameImage, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    return templates.TemplateResponse("admin/game_form.html", {
        "request": request,
        "user": user,
        "game": game
    })


@router.post("/games/{game_id}/edit", summary="Update Game", description="Update a game image (Admin only)")
async def update_game(
    game_id: int,
    request: Request,
    friendly_name: str = Form(...),
    docker_image: str = Form(...),
    default_internal_port: int = Form(...),
    min_ram: str = Form(...),
    min_cpu: str = Form(...),
    protocol: str = Form("tcp"),
    description: Optional[str] = Form(None),
    icon_url: str = Form("/static/img/default_icon.png"),
    wallpaper_url: str = Form("/static/img/default_wallpaper.jpg"),
    user: User = Depends(require_auth_admin),
    session: Session = Depends(get_session)
):
    game = session.get(GameImage, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game.friendly_name = friendly_name
    game.docker_image = docker_image
    game.default_internal_port = default_internal_port
    game.min_ram = min_ram
    game.min_cpu = min_cpu
    game.protocol = protocol
    game.description = description
    game.icon_url = icon_url
    game.wallpaper_url = wallpaper_url
    
    session.add(game)
    session.commit()
    
    logger.info(f"Updated game image: {friendly_name} by {user.email}")
    
    return RedirectResponse(url="/admin/games", status_code=303)


@router.post("/games/{game_id}/delete", summary="Delete Game", description="Delete a game image (Admin only)")
async def delete_game(
    game_id: int,
    user: User = Depends(require_auth_admin),
    session: Session = Depends(get_session)
):
    game = session.get(GameImage, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    session.delete(game)
    session.commit()
    
    logger.info(f"Deleted game image: {game.friendly_name} by {user.email}")
    
    return RedirectResponse(url="/admin/games", status_code=303)
