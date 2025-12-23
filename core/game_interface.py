from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class GameConfig:
    docker_image: str
    default_port: int
    min_ram: str
    min_cpu: str
    protocol: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    wallpaper_url: Optional[str] = None
    env_vars_schema: Optional[Dict] = None


@dataclass
class PlayerInfo:
    online: bool
    current: int
    max: int
    players: Optional[List[str]] = None


class GameInterface(ABC):
    @abstractmethod
    def get_config(self) -> GameConfig:
        """
        Returns static game configuration.
        """
        pass
    
    @abstractmethod
    async def get_player_count(self, ip: str, port: int) -> PlayerInfo:
        """
        Query game server for player count.
        Returns PlayerInfo with current/max players and optional player list.
        """
        pass
    
    @abstractmethod
    async def run_self_test(self) -> Dict[str, any]:
        """
        Health check for the game plugin.
        Returns dict with:
        - success (bool)
        - message (str)
        - details (dict)
        """
        pass
    
    def get_display_name(self) -> str:
        """Human-readable game name"""
        return self.__class__.__module__.split('.')[1].replace('_', ' ').title()
    
    def get_plugin_id(self) -> str:
        """Unique identifier for this plugin"""
        return self.__class__.__module__.split('.')[1]
