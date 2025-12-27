import docker
import docker.errors
import logging
import tarfile
import io
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DockerManager:
    def __init__(self):
        self.client = docker.from_env()
    
    def _build_proxy_image(self):
        logger.info("Building gsp-proxy:latest image")
        try:
            self.client.images.get("gsp-proxy:latest")
            logger.info("Proxy image already exists")
            return
        except docker.errors.ImageNotFound:
            pass
        
        dockerfile_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "proxy_service")
        if not os.path.exists(dockerfile_path):
            logger.warning(f"Proxy service path not found: {dockerfile_path}")
            return
        
        try:
            self.client.images.build(
                path=dockerfile_path,
                tag="gsp-proxy:latest",
                rm=True,
                forcerm=True
            )
            logger.info("Proxy image built successfully")
        except Exception as e:
            logger.error(f"Failed to build proxy image: {e}")
    
    def deploy_server(self, server_id: int, game_image: str, friendly_name: str, 
                      port: int, protocol: str, env_vars: Dict[str, str],
                      min_ram: str, min_cpu: str, webhook_config: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Deploying server {server_id} - {friendly_name}")
        
        try:
            network_name = f"net-{server_id}"
            
            try:
                self.client.networks.get(network_name)
                logger.info(f"Network {network_name} already exists")
            except docker.errors.NotFound:
                self.client.networks.create(
                    network_name,
                    driver="bridge",
                    internal=False
                )
                logger.info(f"Created network {network_name}")
            
            self._build_proxy_image()
            
            game_container_name = f"game-{server_id}"
            proxy_container_name = f"proxy-{server_id}"
            
            try:
                self.client.containers.get(game_container_name)
                self.client.containers.get(proxy_container_name)
                logger.warning(f"Containers for server {server_id} already exist")
                return {"error": "Containers already exist"}
            except docker.errors.NotFound:
                pass
            
            public_port = self._get_available_port()
            
            proxy_env = {
                "TARGET_HOST": game_container_name,
                "TARGET_PORT": str(port),
                "PROTOCOL": protocol.upper(),
                "LISTEN_PORT": str(port)
            }
            
            if webhook_config.get("enabled"):
                proxy_env.update({
                    "BACKEND_WEBHOOK_URL": f"{webhook_config.get('backend_url', '')}/api/webhook/wake",
                    "SERVER_ID": str(server_id),
                    "WEBHOOK_TOKEN": webhook_config.get("webhook_secret", "")
                })
            
            try:
                proxy_container = self.client.containers.run(
                    "gsp-proxy:latest",
                    name=proxy_container_name,
                    network=network_name,
                    ports={f"{port}/tcp": public_port, f"{port}/udp": public_port},
                    environment=proxy_env,
                    restart_policy={"Name": "always"},
                    detach=True,
                    mem_limit="50m",
                    cpu_quota=50000,
                    cpu_period=100000
                )
                logger.info(f"Started proxy container {proxy_container.id}")
            except Exception as e:
                logger.error(f"Failed to start proxy container: {e}")
                return {"error": f"Failed to start proxy: {e}"}
            
            volume_name = f"game-data-{server_id}"
            try:
                self.client.volumes.get(volume_name)
            except docker.errors.NotFound:
                self.client.volumes.create(volume_name)
                logger.info(f"Created volume {volume_name}")
            
            game_mounts = {
                volume_name: {"bind": "/data", "mode": "rw"}
            }
            
            game_env = env_vars.copy()
            game_env.update({
                "SERVER_ID": str(server_id),
                "DATA_DIR": "/data"
            })
            
            try:
                game_container = self.client.containers.create(
                    game_image,
                    name=game_container_name,
                    network=network_name,
                    volumes=game_mounts,
                    environment=game_env,
                    mem_limit=min_ram,
                    cpu_quota=int(float(min_cpu) * 100000),
                    cpu_period=100000
                )
                logger.info(f"Created game container {game_container.id}")
            except Exception as e:
                logger.error(f"Failed to create game container: {e}")
                proxy_container.remove(force=True)
                return {"error": f"Failed to create game container: {e}"}
            
            return {
                "success": True,
                "proxy_container_id": proxy_container.id,
                "game_container_id": game_container.id,
                "network_name": network_name,
                "public_port": public_port
            }
            
        except Exception as e:
            logger.error(f"Failed to deploy server {server_id}: {e}")
            return {"error": str(e)}
    
    def wake_server(self, server_id: int, game_container_id: str) -> bool:
        logger.info(f"Waking server {server_id}")
        
        try:
            game_container = self.client.containers.get(game_container_id)
            
            if game_container.status != "running":
                game_container.start()
                logger.info(f"Started game container {game_container_id}")
            
            return True
            
        except docker.errors.APIError as e:
            logger.error(f"Failed to wake server {server_id}: {e}")
            return False
    
    def hibernate_server(self, server_id: int, game_container_id: str) -> bool:
        logger.info(f"Hibernating server {server_id}")
        
        try:
            game_container = self.client.containers.get(game_container_id)
            
            if game_container.status == "running":
                game_container.stop(timeout=30)
                logger.info(f"Stopped game container {game_container_id}")
            
            return True
            
        except docker.errors.APIError as e:
            logger.error(f"Failed to hibernate server {server_id}: {e}")
            return False
    
    def delete_server(self, server_id: int, game_container_id: str, 
                      proxy_container_id: str, network_name: str) -> bool:
        logger.info(f"Deleting server {server_id}")
        
        try:
            if game_container_id:
                try:
                    game_container = self.client.containers.get(game_container_id)
                    game_container.remove(force=True)
                    logger.info(f"Removed game container {game_container_id}")
                except docker.errors.NotFound:
                    pass
            
            if proxy_container_id:
                try:
                    proxy_container = self.client.containers.get(proxy_container_id)
                    proxy_container.remove(force=True)
                    logger.info(f"Removed proxy container {proxy_container_id}")
                except docker.errors.NotFound:
                    pass
            
            if network_name:
                try:
                    network = self.client.networks.get(network_name)
                    network.remove()
                    logger.info(f"Removed network {network_name}")
                except docker.errors.NotFound:
                    pass
            
            volume_name = f"game-data-{server_id}"
            try:
                volume = self.client.volumes.get(volume_name)
                volume.remove()
                logger.info(f"Removed volume {volume_name}")
            except docker.errors.NotFound:
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete server {server_id}: {e}")
            return False
    
    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode('utf-8') if logs else ""
        except docker.errors.APIError as e:
            logger.error(f"Failed to get logs for container {container_id}: {e}")
            return f"Error retrieving logs: {e}"
    
    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0
            
            memory_usage = stats['memory_stats'].get('usage', 0)
            memory_limit = stats['memory_stats'].get('limit', 1)
            memory_percent = (memory_usage / memory_limit) * 100
            
            return {
                'cpu_percent': round(cpu_percent, 2),
                'memory_percent': round(memory_percent, 2),
                'memory_used_mb': round(memory_usage / (1024 * 1024), 2),
                'status': container.status
            }
        except Exception as e:
            logger.error(f"Failed to get stats for container {container_id}: {e}")
            return {
                'cpu_percent': 0,
                'memory_percent': 0,
                'memory_used_mb': 0,
                'status': 'unknown'
            }
    
    def _get_available_port(self) -> int:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
