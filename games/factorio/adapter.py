import asyncio
import logging
from core.game_interface import GameInterface, GameConfig, PlayerInfo


logger = logging.getLogger(__name__)


class FactorioAdapter(GameInterface):
    def __init__(self):
        self.config = None
    
    def get_config(self) -> GameConfig:
        """Return static Factorio configuration"""
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
                env_vars_schema=data.get('env_vars_schema'),
                display_name=data.get('display_name')
            )
        
        return self.config
    
    async def get_player_count(self, ip: str, port: int) -> PlayerInfo:
        """Query Factorio server using RCON"""
        try:
            from rcon import rcon
            from rcon.exceptions import RCONError
            
            # Factorio uses RCON on port 27015 by default
            rcon_port = 27015
            rcon_password = "password"  # Default, should be configurable
            
            try:
                response = await asyncio.to_thread(
                    rcon,
                    "/players",
                    host=ip,
                    port=rcon_port,
                    password=rcon_password
                )
                
                # Parse response: "Online players (N): Player1, Player2, ..."
                if "Online players" in response:
                    parts = response.split("(")[1].split(")")[0]
                    current = int(parts.strip())
                    return PlayerInfo(
                        online=True,
                        current=current,
                        max=20,
                        players=None
                    )
            except RCONError:
                pass
            
            # Fallback: return online status without count
            return PlayerInfo(
                online=True,
                current=0,
                max=20,
                players=None
            )
            
        except ImportError:
            logger.warning("python-rcon not installed")
            return PlayerInfo(online=False, current=0, max=0)
        except Exception as e:
            logger.error(f"Factorio query failed: {e}")
            return PlayerInfo(online=False, current=0, max=0)
    
    async def run_self_test(self) -> dict:
        """Health check for Factorio plugin"""
        results = {
            'success': True,
            'message': 'Factorio adapter healthy',
            'details': {}
        }
        
        try:
            config = self.get_config()
            results['details']['config'] = 'OK'
            
            try:
                from rcon import rcon
                results['details']['rcon'] = 'Installed'
            except ImportError:
                results['warnings'] = ['python-rcon not installed. Player counts will not work.']
                results['details']['rcon'] = 'Missing'
            
            try:
                import docker
                client = docker.from_env()
                try:
                    client.images.get(config.docker_image)
                    results['details']['docker_image'] = f'Found: {config.docker_image}'
                except Exception:
                    results['warnings'] = results.get('warnings', []) + ['Docker image not found locally. Will be pulled on first deploy.']
                    results['details']['docker_image'] = 'Not local (will pull)'
            except ImportError:
                results['success'] = False
                results['message'] = 'Docker Python library not installed'
                results['details']['docker'] = 'Missing'
            
        except Exception as e:
            results['success'] = False
            results['message'] = f'Self-test failed: {str(e)}'
        
        return results
