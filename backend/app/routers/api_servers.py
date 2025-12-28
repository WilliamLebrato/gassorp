from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional
import logging

from ..models import User, Server, GameImage, ServerState
from ..services.auth import get_current_user
from ..services.node_client import NodeClient
from ..database import get_session

router = APIRouter(prefix="/api/servers", tags=["servers"])

node_client: Optional[NodeClient] = None
logger = logging.getLogger(__name__)


def set_node_client(nc: NodeClient):
    global node_client
    node_client = nc


class ServerCreateRequest(BaseModel):
    friendly_name: str
    game_image_id: int
    auto_sleep: bool = False


class ServerResponse(BaseModel):
    id: int
    friendly_name: str
    state: str
    auto_sleep: bool
    public_port: Optional[int]
    created_at: str
    game_image: dict


@router.get("", response_model=list[ServerResponse])
async def list_servers(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    servers = session.exec(
        select(Server).where(Server.user_id == user.id)
    ).all()
    
    result = []
    for server in servers:
        session.refresh(server)
        result.append({
            "id": server.id,
            "friendly_name": server.friendly_name,
            "state": server.state.value,
            "auto_sleep": server.auto_sleep,
            "public_port": server.public_port,
            "created_at": server.created_at.isoformat(),
            "game_image": {
                "id": server.game_image.id,
                "friendly_name": server.game_image.friendly_name,
                "docker_image": server.game_image.docker_image
            }
        })
    
    return result


@router.post("")
async def create_server(
    req: ServerCreateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    game_image = session.get(GameImage, req.game_image_id)
    if not game_image:
        raise HTTPException(status_code=404, detail="Game image not found")
    
    server = Server(
        user_id=user.id,
        game_image_id=req.game_image_id,
        friendly_name=req.friendly_name,
        env_vars={},
        auto_sleep=req.auto_sleep,
        state=ServerState.SLEEPING
    )
    session.add(server)
    session.commit()
    session.refresh(server)
    
    if node_client:
        try:
            result = await node_client.deploy_server(server, game_image)
            server.proxy_container_id = result.get("proxy_container_id")
            server.game_container_id = result.get("game_container_id")
            server.public_port = result.get("public_port")
            server.private_network_name = result.get("network_name")
            session.add(server)
            session.commit()
        except Exception as e:
            logger.error(f"Failed to deploy server {server.id}: {e}")
            session.delete(server)
            session.commit()
            raise HTTPException(status_code=500, detail=f"Failed to deploy server: {e}")
    
    return JSONResponse({
        "id": server.id,
        "friendly_name": server.friendly_name,
        "state": server.state.value,
        "auto_sleep": server.auto_sleep,
        "public_port": server.public_port
    })


@router.get("/{server_id}")
async def get_server(
    server_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    stats = {}
    if node_client:
        stats = await node_client.get_server_stats(server)
    
    return JSONResponse({
        "id": server.id,
        "friendly_name": server.friendly_name,
        "state": server.state.value,
        "auto_sleep": server.auto_sleep,
        "public_port": server.public_port,
        "created_at": server.created_at.isoformat(),
        "game_image": {
            "id": server.game_image.id,
            "friendly_name": server.game_image.friendly_name,
            "docker_image": server.game_image.docker_image
        },
        "stats": stats
    })


@router.post("/{server_id}/wake")
async def wake_server(
    server_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if node_client and user.credits > 0:
        if await node_client.wake_server(server):
            server.state = ServerState.RUNNING
            server.last_state_change = server.last_state_change
            session.add(server)
            session.commit()
    
    return JSONResponse({"success": True})


@router.post("/{server_id}/hibernate")
async def hibernate_server(
    server_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if node_client:
        if await node_client.hibernate_server(server):
            server.state = ServerState.SLEEPING
            server.last_state_change = server.last_state_change
            session.add(server)
            session.commit()
    
    return JSONResponse({"success": True})


@router.delete("/{server_id}")
async def delete_server(
    server_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if node_client:
        await node_client.delete_server(server)
    
    session.delete(server)
    session.commit()
    
    return JSONResponse({"success": True})


@router.get("/{server_id}/logs")
async def get_server_logs(
    server_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    tail: int = 100
):
    server = session.get(Server, server_id)
    if not server or server.user_id != user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if node_client:
        logs = await node_client.get_server_logs(server, tail)
        return JSONResponse({"logs": logs})
    
    return JSONResponse({"logs": "No logs available"})
