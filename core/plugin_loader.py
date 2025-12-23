import importlib
import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass

from .game_interface import GameInterface, GameConfig


logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    ACTIVE = "active"
    WARNING = "warning"
    ERROR = "error"
    DRAFT = "draft"


@dataclass
class PluginInfo:
    id: str
    status: PluginStatus
    display_name: str
    config: Optional[GameConfig] = None
    adapter: Optional[GameInterface] = None
    error_message: Optional[str] = None
    test_results: Optional[Dict] = None


class PluginLoader:
    def __init__(self, games_dir: str = "games"):
        self.games_dir = Path(games_dir)
        self.plugins: Dict[str, PluginInfo] = {}
        self._load_plugins()
    
    def _load_plugins(self):
        """Scan and load all game plugins from games/ directory"""
        if not self.games_dir.exists():
            logger.warning(f"Games directory {self.games_dir} does not exist")
            return
        
        for plugin_dir in self.games_dir.iterdir():
            if not plugin_dir.is_dir() or plugin_dir.name.startswith('_'):
                continue
            
            plugin_id = plugin_dir.name
            plugin_info = self._load_plugin(plugin_dir)
            
            if plugin_info:
                self.plugins[plugin_id] = plugin_info
                logger.info(f"Loaded plugin: {plugin_id} - {plugin_info.status.value}")
    
    def _load_plugin(self, plugin_dir: Path) -> Optional[PluginInfo]:
        """Load a single plugin from its directory"""
        plugin_id = plugin_dir.name
        config_file = plugin_dir / "config.json"
        adapter_file = plugin_dir / "adapter.py"
        
        if not config_file.exists():
            return PluginInfo(
                id=plugin_id,
                status=PluginStatus.ERROR,
                display_name=self._format_display_name(plugin_id),
                error_message="config.json not found"
            )
        
        if not adapter_file.exists():
            return PluginInfo(
                id=plugin_id,
                status=PluginStatus.DRAFT,
                display_name=self._format_display_name(plugin_id),
                error_message="adapter.py not found (Draft mode)"
            )
        
        try:
            config = self._load_config(config_file)
            adapter = self._load_adapter(adapter_file, plugin_id)
            
            if adapter:
                test_results = await self._run_self_test(adapter)
                
                status = PluginStatus.ACTIVE
                if not test_results.get('success'):
                    status = PluginStatus.WARNING
                
                return PluginInfo(
                    id=plugin_id,
                    status=status,
                    display_name=config.get('display_name', self._format_display_name(plugin_id)),
                    config=config,
                    adapter=adapter,
                    test_results=test_results
                )
            
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_id}: {str(e)}")
            return PluginInfo(
                id=plugin_id,
                status=PluginStatus.ERROR,
                display_name=self._format_display_name(plugin_id),
                error_message=str(e)
            )
    
    def _load_config(self, config_file: Path) -> GameConfig:
        """Load and validate config.json"""
        with open(config_file, 'r') as f:
            data = json.load(f)
        
        return GameConfig(
            docker_image=data['docker_image'],
            default_port=data['default_port'],
            min_ram=data['min_ram'],
            min_cpu=data['min_cpu'],
            protocol=data.get('protocol', 'tcp'),
            description=data.get('description'),
            icon_url=data.get('icon_url'),
            wallpaper_url=data.get('wallpaper_url'),
            env_vars_schema=data.get('env_vars_schema')
        )
    
    def _load_adapter(self, adapter_file: Path, plugin_id: str) -> Optional[GameInterface]:
        """Dynamically load adapter.py"""
        spec = importlib.util.spec_from_file_location(
            f"games.{plugin_id}.adapter",
            adapter_file
        )
        
        if not spec or not spec.loader:
            raise ImportError(f"Cannot load adapter from {adapter_file}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, GameInterface) and attr != GameInterface:
                return attr()
        
        raise ImportError(f"No GameInterface subclass found in {adapter_file}")
    
    async def _run_self_test(self, adapter: GameInterface) -> Dict:
        """Run adapter self-test"""
        try:
            return await adapter.run_self_test()
        except Exception as e:
            return {
                'success': False,
                'message': f"Self-test failed: {str(e)}",
                'details': {}
            }
    
    def _format_display_name(self, plugin_id: str) -> str:
        """Format plugin ID for display"""
        return plugin_id.replace('_', ' ').title()
    
    def get_all_plugins(self) -> Dict[str, PluginInfo]:
        """Get all loaded plugins"""
        return self.plugins
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        """Get specific plugin by ID"""
        return self.plugins.get(plugin_id)
    
    def get_active_plugins(self) -> Dict[str, PluginInfo]:
        """Get only active (non-error) plugins"""
        return {
            k: v for k, v in self.plugins.items()
            if v.status in [PluginStatus.ACTIVE, PluginStatus.WARNING]
        }
    
    def reload_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        """Reload a specific plugin"""
        plugin_dir = self.games_dir / plugin_id
        if plugin_dir.exists():
            plugin_info = self._load_plugin(plugin_dir)
            if plugin_info:
                self.plugins[plugin_id] = plugin_info
                return plugin_info
        return None
