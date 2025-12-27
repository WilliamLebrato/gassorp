from typing import Optional, Dict, List
from dataclasses import dataclass
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class PlayerInfo:
    current: int
    max: int
    players: Optional[List[Dict[str, str]]] = None


class GameQueryService:
    def __init__(self):
        pass
    
    async def get_player_count(
        self, 
        host: str, 
        port: int, 
        protocol: str = "tcp"
    ) -> Optional[PlayerInfo]:
        try:
            if protocol == "minecraft":
                return await self._query_minecraft(host, port)
            else:
                return await self._query_valve(host, port)
        except Exception as e:
            logger.error(f"Failed to query {host}:{port}: {str(e)}")
            return None
    
    async def _query_minecraft(self, host: str, port: int) -> Optional[PlayerInfo]:
        try:
            from mcstatus import JavaServer
            
            server = JavaServer.lookup(f"{host}:{port}")
            status = await asyncio.wait_for(server.async_status(), timeout=5)
            
            players_list = None
            if status.players.sample:
                players_list = [
                    {"name": player.name for player in status.players.sample}
                ]
            
            return PlayerInfo(
                current=status.players.online,
                max=status.players.max,
                players=players_list
            )
        except ImportError:
            logger.error("mcstatus not installed. Install with: pip install mcstatus")
            return None
        except Exception as e:
            logger.error(f"Minecraft query failed: {str(e)}")
            return None
    
    async def _query_valve(self, host: str, port: int) -> Optional[PlayerInfo]:
        try:
            import a2s
            
            info = await asyncio.wait_for(
                a2s.ainfo((host, port), timeout=5),
                timeout=5
            )
            
            players = await asyncio.wait_for(
                a2s.aplayers((host, port), timeout=5),
                timeout=5
            )
            
            players_list = [
                {"name": p.name, "score": p.score, "duration": p.duration}
                for p in players
            ] if players else None
            
            return PlayerInfo(
                current=info.player_count,
                max=info.max_players,
                players=players_list
            )
        except ImportError:
            logger.error("python-a2s not installed. Install with: pip install python-a2s")
            return None
        except Exception as e:
            logger.error(f"Valve query failed: {str(e)}")
            return None
