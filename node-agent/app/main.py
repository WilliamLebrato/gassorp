from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import os
from dotenv import load_dotenv

from core.docker_manager import DockerManager

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NODE_SECRET = os.getenv("SECRET_KEY", "dev_secret")
docker_manager = DockerManager()

app = FastAPI(
    title="GSP Node Agent",
    description="Remote Docker executor for GSP nodes",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_node_secret(x_node_secret: str = Header(...)):
    if x_node_secret != NODE_SECRET:
        raise HTTPException(status_code=403, detail="Invalid node secret")
    return True


class DeployRequest(BaseModel):
    server_id: int
    game_image: str
    friendly_name: str
    port: int
    protocol: str
    env_vars: Dict[str, str]
    min_ram: str
    min_cpu: str
    webhook_config: Dict[str, Any]


@app.post("/deploy")
async def deploy_server(req: DeployRequest, _: bool = Depends(verify_node_secret)):
    logger.info(f"Deploy request for server {req.server_id}")
    
    result = docker_manager.deploy_server(
        server_id=req.server_id,
        game_image=req.game_image,
        friendly_name=req.friendly_name,
        port=req.port,
        protocol=req.protocol,
        env_vars=req.env_vars,
        min_ram=req.min_ram,
        min_cpu=req.min_cpu,
        webhook_config=req.webhook_config
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return JSONResponse(result)


@app.post("/servers/{server_id}/wake")
async def wake_server(server_id: int, game_container_id: str, _: bool = Depends(verify_node_secret)):
    logger.info(f"Wake request for server {server_id}")
    
    success = docker_manager.wake_server(server_id, game_container_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to wake server")
    
    return JSONResponse({"success": True})


@app.post("/servers/{server_id}/hibernate")
async def hibernate_server(server_id: int, game_container_id: str, _: bool = Depends(verify_node_secret)):
    logger.info(f"Hibernate request for server {server_id}")
    
    success = docker_manager.hibernate_server(server_id, game_container_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to hibernate server")
    
    return JSONResponse({"success": True})


@app.delete("/servers/{server_id}")
async def delete_server(
    server_id: int,
    game_container_id: str,
    proxy_container_id: str,
    network_name: str,
    _: bool = Depends(verify_node_secret)
):
    logger.info(f"Delete request for server {server_id}")
    
    success = docker_manager.delete_server(
        server_id, game_container_id, proxy_container_id, network_name
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete server")
    
    return JSONResponse({"success": True})


@app.get("/servers/{server_id}/stats")
async def get_server_stats(server_id: int, game_container_id: str, _: bool = Depends(verify_node_secret)):
    logger.info(f"Stats request for server {server_id}")
    
    stats = docker_manager.get_container_stats(game_container_id)
    
    return JSONResponse(stats)


@app.get("/servers/{server_id}/logs")
async def get_server_logs(
    server_id: int,
    game_container_id: str,
    tail: int = 100,
    _: bool = Depends(verify_node_secret)
):
    logger.info(f"Logs request for server {server_id}")
    
    logs = docker_manager.get_container_logs(game_container_id, tail)
    
    return JSONResponse({"logs": logs})


@app.get("/health")
async def health_check():
    return JSONResponse({"status": "healthy"})


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
        port=8001,
        reload=True
    )
