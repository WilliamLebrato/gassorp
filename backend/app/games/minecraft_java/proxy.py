import logging
from core.proxy_base import ProxyBase


logger = logging.getLogger(__name__)


class MinecraftProxy(ProxyBase):
    """
    Minecraft-specific smart proxy.
    Handles wake-on-connect and traffic inspection.
    """
    
    def __init__(self, target_host: str, target_port: int, proxy_port: int):
        super().__init__(target_host, target_port, proxy_port, protocol="tcp")
    
    async def on_connect(self, client_addr: tuple):
        """
        Minecraft handshake detection.
        Send wake signal immediately on connection.
        """
        logger.info(f"Minecraft client connecting from {client_addr}")
        
        if self.state == ProxyState.SLEEPING and self.on_wake_callback:
            logger.info("Waking Minecraft server...")
            await self.on_wake_callback()
    
    async def inspect_traffic(self, data: bytes, client_to_server: bool) -> bytes:
        """
        Inspect Minecraft packets.
        Packet format: [Length] [PacketID] [Data]
        
        Handshake packet ID: 0x00
        Login Start packet ID: 0x00
        """
        if len(data) < 1:
            return data
        
        try:
            packet_id = data[0] if len(data) > 0 else 0
            
            if client_to_server:
                if packet_id == 0x00:
                    logger.debug("Minecraft handshake/login detected")
            
            return data
        except Exception as e:
            logger.error(f"Error inspecting Minecraft traffic: {e}")
            return data
