import logging
from core.proxy_base import ProxyBase


logger = logging.getLogger(__name__)


class FactorioProxy(ProxyBase):
    """
    Factorio-specific smart proxy.
    Factorio uses UDP.
    """
    
    def __init__(self, target_host: str, target_port: int, proxy_port: int):
        super().__init__(target_host, target_port, proxy_port, protocol="udp")
    
    async def on_connect(self, client_addr: tuple):
        """
        Factorio client detection.
        Wake server on first packet from new client.
        """
        logger.info(f"Factorio client connecting from {client_addr}")
        
        if self.state == ProxyState.SLEEPING and self.on_wake_callback:
            logger.info("Waking Factorio server...")
            await self.on_wake_callback()
    
    async def inspect_traffic(self, data: bytes, client_to_server: bool) -> bytes:
        """
        Inspect Factorio UDP packets.
        Factorio uses a custom UDP protocol.
        
        For now, we just pass through traffic.
        """
        if len(data) < 1:
            return data
        
        try:
            if client_to_server:
                logger.debug(f"Factorio packet: {len(data)} bytes")
            
            return data
        except Exception as e:
            logger.error(f"Error inspecting Factorio traffic: {e}")
            return data
