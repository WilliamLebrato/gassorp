import logging
from core.proxy_base import ProxyBase


logger = logging.getLogger(__name__)


class TerrariaProxy(ProxyBase):
    """
    Terraria-specific smart proxy.
    Terraria/TShock uses TCP.
    """
    
    def __init__(self, target_host: str, target_port: int, proxy_port: int):
        super().__init__(target_host, target_port, proxy_port, protocol="tcp")
    
    async def on_connect(self, client_addr: tuple):
        """
        Terraria client detection.
        Wake server on first connection.
        """
        logger.info(f"Terraria client connecting from {client_addr}")
        
        if self.state == ProxyState.SLEEPING and self.on_wake_callback:
            logger.info("Waking Terraria server...")
            await self.on_wake_callback()
    
    async def inspect_traffic(self, data: bytes, client_to_server: bool) -> bytes:
        """
        Inspect Terraria packets.
        Terraria uses a custom packet protocol.
        
        For now, we just pass through traffic.
        """
        if len(data) < 1:
            return data
        
        try:
            if client_to_server:
                first_byte = data[0]
                logger.debug(f"Terraria packet: {first_byte}")
            
            return data
        except Exception as e:
            logger.error(f"Error inspecting Terraria traffic: {e}")
            return data
