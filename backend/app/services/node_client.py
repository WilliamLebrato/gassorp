import httpx
import logging
from typing import Optional, Dict, Any
from ..models import Server, GameImage

logger = logging.getLogger(__name__)


class NodeClient:
    def __init__(self, base_url: str, secret: str):
        self.base_url = base_url.rstrip('/')
        self.secret = secret
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def deploy_server(self, server: Server, game_image: GameImage) -> Dict[str, Any]:
        logger.info(f"Deploying server {server.id} via Node Agent")
        
        payload = {
            "server_id": server.id,
            "game_image": game_image.docker_image,
            "friendly_name": server.friendly_name,
            "port": game_image.default_internal_port,
            "protocol": game_image.protocol,
            "env_vars": server.env_vars,
            "min_ram": game_image.min_ram,
            "min_cpu": game_image.min_cpu,
            "webhook_config": {
                "enabled": True,
                "backend_url": "",
                "webhook_secret": self.secret
            }
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/deploy",
                json=payload,
                headers={"X-Node-Secret": self.secret}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Server {server.id} deployed successfully: {result}")
            return result
        except httpx.HTTPError as e:
            logger.error(f"Failed to deploy server {server.id}: {e}")
            raise
    
    async def wake_server(self, server: Server) -> bool:
        logger.info(f"Waking server {server.id} via Node Agent")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/servers/{server.id}/wake",
                headers={"X-Node-Secret": self.secret}
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to wake server {server.id}: {e}")
            return False
    
    async def hibernate_server(self, server: Server) -> bool:
        logger.info(f"Hibernating server {server.id} via Node Agent")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/servers/{server.id}/hibernate",
                headers={"X-Node-Secret": self.secret}
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to hibernate server {server.id}: {e}")
            return False
    
    async def delete_server(self, server: Server) -> bool:
        logger.info(f"Deleting server {server.id} via Node Agent")
        
        try:
            response = await self.client.delete(
                f"{self.base_url}/servers/{server.id}",
                headers={"X-Node-Secret": self.secret}
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete server {server.id}: {e}")
            return False
    
    async def get_server_stats(self, server: Server) -> Dict[str, Any]:
        logger.info(f"Getting stats for server {server.id} via Node Agent")
        
        try:
            response = await self.client.get(
                f"{self.base_url}/servers/{server.id}/stats",
                headers={"X-Node-Secret": self.secret}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get stats for server {server.id}: {e}")
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "memory_used_mb": 0,
                "status": "unknown"
            }
    
    async def get_server_logs(self, server: Server, tail: int = 100) -> str:
        logger.info(f"Getting logs for server {server.id} via Node Agent")
        
        try:
            response = await self.client.get(
                f"{self.base_url}/servers/{server.id}/logs?tail={tail}",
                headers={"X-Node-Secret": self.secret}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("logs", "")
        except httpx.HTTPError as e:
            logger.error(f"Failed to get logs for server {server.id}: {e}")
            return f"Error retrieving logs: {e}"
    
    async def close(self):
        await self.client.aclose()
