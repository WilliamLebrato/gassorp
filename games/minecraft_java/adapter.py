import asyncio
import logging
from core.game_interface import GameInterface, GameConfig, PlayerInfo


logger = logging.getLogger(__name__)


class MinecraftJavaAdapter(GameInterface):
    def __init__(self):
        self.config = None
    
    def get_config(self) -> GameConfig:
        """Return static Minecraft configuration"""
        if not self.config:
            import json
            
            config_path = __file__.replace('adapter.py', 'config.json')
            with open(config_path, 'r') as f:
                data = json.load(f)
            
            self.config = GameConfig(
                docker_image=data['docker_image'],
                default_port=data['default_port'],
                min_ram=data['min_ram'],
                min_cpu=data['min_cpu'],
                protocol=data['protocol'],
                description=data.get('description'),
                icon_url=data.get('icon_url'),
                wallpaper_url=data.get('wallpaper_url'),
                env_vars_schema=data.get('env_vars_schema')
            )
        
        return self.config
    
    async def get_player_count(self, ip: str, port: int) -> PlayerInfo:
        """Query Minecraft server for player count using mcstatus"""
        try:
            from mcstatus import JavaServer
            
            server = JavaServer.lookup(f"{ip}:{port}")
            status = await asyncio.wait_for(server.async_status(), timeout=5)
            
            players_list = None
            if status.players.sample:
                players_list = [p.name for p in status.players.sample]
            
            return PlayerInfo(
                online=True,
                current=status.players.online,
                max=status.players.max,
                players=players_list
            )
        except ImportError:
            logger.error("mcstatus not installed")
            return PlayerInfo(online=False, current=0, max=0)
        except Exception as e:
            logger.error(f"Minecraft query failed: {e}")
            return PlayerInfo(online=False, current=0, max=0)
    
    async def run_self_test(self) -> dict:
        """Health check for Minecraft plugin"""
        results = {
            'success': True,
            'message': 'Minecraft adapter healthy',
            'details': {}
        }
        
        try:
            config = self.get_config()
            results['details']['config'] = 'OK'
            
            try:
                from mcstatus import JavaServer
                results['details']['mcstatus'] = 'Installed'
            except ImportError:
                results['success'] = False
                results['message'] = 'mcstatus library not installed'
                results['details']['mcstatus'] = 'Missing'
            
            try:
                import docker
                client = docker.from_env()
                try:
                    client.images.get(config.docker_image)
                    results['details']['docker_image'] = f'Found: {config.docker_image}'
                except Exception:
                    results['warnings'] = ['Docker image not found locally. Will be pulled on first deploy.']
                    results['details']['docker_image'] = 'Not local (will pull)'
            except ImportError:
                results['success'] = False
                results['message'] = 'Docker Python library not installed'
                results['details']['docker'] = 'Missing'
            
        except Exception as e:
            results['success'] = False
            results['message'] = f'Self-test failed: {str(e)}'
        
        return results
