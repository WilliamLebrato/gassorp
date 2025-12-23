import docker
import docker.errors
import logging
import tarfile
import io
import os
from typing import Optional
from google.cloud import storage
from models import Server, ServerState, GameImage

logger = logging.getLogger(__name__)


class SidecarManager:
    def __init__(self, webhook_secret: str, backend_url: str, gcs_bucket: str):
        self.client = docker.from_env()
        self.webhook_secret = webhook_secret
        self.backend_url = backend_url
        self.gcs_bucket = gcs_bucket
        self.gcs_client = None
    
    def _ensure_gcs_client(self):
        if self.gcs_client is None:
            self.gcs_client = storage.Client()
    
    def _build_proxy_image(self):
        logger.info("Building gsp-proxy:latest image")
        try:
            self.client.images.get("gsp-proxy:latest")
            logger.info("Proxy image already exists")
            return
        except docker.errors.ImageNotFound:
            pass
        
        dockerfile_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "proxy_service")
        self.client.images.build(
            path=dockerfile_path,
            tag="gsp-proxy:latest",
            rm=True,
            forcerm=True
        )
        logger.info("Proxy image built successfully")
    
    def deploy(self, server: Server, game_image: GameImage) -> bool:
        logger.info(f"Deploying server {server.id} - {server.friendly_name}")
        
        try:
            network_name = f"net-{server.id}"
            
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
            
            game_container_name = f"game-{server.id}"
            proxy_container_name = f"proxy-{server.id}"
            
            try:
                self.client.containers.get(game_container_name)
                self.client.containers.get(proxy_container_name)
                logger.warning(f"Containers for server {server.id} already exist")
                return False
            except docker.errors.NotFound:
                pass
            
            public_port = self._get_available_port()
            
            proxy_env = {
                "TARGET_HOST": game_container_name,
                "TARGET_PORT": str(game_image.default_internal_port),
                "BACKEND_WEBHOOK_URL": f"{self.backend_url}/api/webhook/wake",
                "SERVER_ID": str(server.id),
                "WEBHOOK_TOKEN": self.webhook_secret,
                "PROTOCOL": game_image.protocol.upper(),
                "LISTEN_PORT": str(game_image.default_internal_port)
            }
            
            proxy_container = self.client.containers.run(
                "gsp-proxy:latest",
                name=proxy_container_name,
                network=network_name,
                ports={f"{game_image.default_internal_port}/tcp": public_port,
                       f"{game_image.default_internal_port}/udp": public_port},
                environment=proxy_env,
                restart_policy={"Name": "always"},
                detach=True,
                mem_limit="50m",
                cpu_quota=50000,
                cpu_period=100000
            )
            logger.info(f"Started proxy container {proxy_container.id}")
            
            volume_name = f"game-data-{server.id}"
            try:
                self.client.volumes.get(volume_name)
            except docker.errors.NotFound:
                self.client.volumes.create(volume_name)
                logger.info(f"Created volume {volume_name}")
            
            game_mounts = {
                volume_name: {"bind": "/data", "mode": "rw"}
            }
            
            game_env = server.env_vars.copy()
            game_env.update({
                "SERVER_ID": str(server.id),
                "DATA_DIR": "/data"
            })
            
            game_container = self.client.containers.create(
                game_image.docker_image,
                name=game_container_name,
                network=network_name,
                volumes=game_mounts,
                environment=game_env,
                mem_limit=game_image.min_ram,
                cpu_quota=int(float(game_image.min_cpu) * 100000),
                cpu_period=100000
            )
            logger.info(f"Created game container {game_container.id}")
            
            server.proxy_container_id = proxy_container.id
            server.game_container_id = game_container.id
            server.private_network_name = network_name
            server.public_port = public_port
            server.state = ServerState.SLEEPING
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to deploy server {server.id}: {e}")
            return False
    
    def wake(self, server: Server) -> bool:
        logger.info(f"Waking server {server.id}")
        
        if server.state == ServerState.RUNNING:
            logger.warning(f"Server {server.id} is already running")
            return True
        
        try:
            game_container = self.client.containers.get(server.game_container_id)
            
            if game_container.status != "running":
                game_container.start()
                logger.info(f"Started game container {server.game_container_id}")
            
            server.state = ServerState.RUNNING
            return True
            
        except docker.errors.APIError as e:
            logger.error(f"Failed to wake server {server.id}: {e}")
            return False
    
    def hibernate(self, server: Server) -> bool:
        logger.info(f"Hibernating server {server.id}")
        
        if server.state == ServerState.SLEEPING:
            logger.warning(f"Server {server.id} is already sleeping")
            return True
        
        try:
            game_container = self.client.containers.get(server.game_container_id)
            
            if game_container.status == "running":
                game_container.stop(timeout=30)
                logger.info(f"Stopped game container {server.game_container_id}")
            
            server.state = ServerState.SLEEPING
            return True
            
        except docker.errors.APIError as e:
            logger.error(f"Failed to hibernate server {server.id}: {e}")
            return False
    
    def delete(self, server: Server) -> bool:
        logger.info(f"Deleting server {server.id}")
        
        try:
            if server.game_container_id:
                try:
                    game_container = self.client.containers.get(server.game_container_id)
                    game_container.remove(force=True)
                    logger.info(f"Removed game container {server.game_container_id}")
                except docker.errors.NotFound:
                    pass
            
            if server.proxy_container_id:
                try:
                    proxy_container = self.client.containers.get(server.proxy_container_id)
                    proxy_container.remove(force=True)
                    logger.info(f"Removed proxy container {server.proxy_container_id}")
                except docker.errors.NotFound:
                    pass
            
            if server.private_network_name:
                try:
                    network = self.client.networks.get(server.private_network_name)
                    network.remove()
                    logger.info(f"Removed network {server.private_network_name}")
                except docker.errors.NotFound:
                    pass
            
            volume_name = f"game-data-{server.id}"
            try:
                volume = self.client.volumes.get(volume_name)
                volume.remove()
                logger.info(f"Removed volume {volume_name}")
            except docker.errors.NotFound:
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete server {server.id}: {e}")
            return False
    
    def export_data(self, server: Server) -> Optional[str]:
        logger.info(f"Exporting data for server {server.id}")
        
        was_running = server.state == ServerState.RUNNING
        
        try:
            if was_running:
                self.hibernate(server)
            
            volume_name = f"game-data-{server.id}"
            volume = self.client.volumes.get(volume_name)
            
            tar_stream, _ = volume.get({}, '/')
            
            tar_buffer = io.BytesIO()
            for chunk in tar_stream:
                tar_buffer.write(chunk)
            tar_buffer.seek(0)
            
            timestamp = int(datetime.now().timestamp())
            blob_name = f"server-{server.id}/backup-{timestamp}.tar.gz"
            
            self._ensure_gcs_client()
            bucket = self.gcs_client.bucket(self.gcs_bucket)
            blob = bucket.blob(blob_name)
            blob.upload_from_file(tar_buffer, content_type="application/gzip")
            
            logger.info(f"Uploaded backup to {blob_name}")
            
            if was_running:
                self.wake(server)
            
            return blob_name
            
        except Exception as e:
            logger.error(f"Failed to export data for server {server.id}: {e}")
            if was_running:
                self.wake(server)
            return None
    
    def get_container_logs(self, server: Server, tail: int = 100) -> str:
        try:
            game_container = self.client.containers.get(server.game_container_id)
            logs = game_container.logs(tail=tail, timestamps=True)
            return logs.decode('utf-8') if logs else ""
        except docker.errors.APIError as e:
            logger.error(f"Failed to get logs for server {server.id}: {e}")
            return f"Error retrieving logs: {e}"
    
    def get_container_stats(self, server: Server) -> dict:
        try:
            game_container = self.client.containers.get(server.game_container_id)
            stats = game_container.stats(stream=False)
            
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
                'status': game_container.status
            }
        except Exception as e:
            logger.error(f"Failed to get stats for server {server.id}: {e}")
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


from datetime import datetime
