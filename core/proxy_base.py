import asyncio
import logging
from typing import Optional, Callable
from enum import Enum


class ProxyState(Enum):
    SLEEPING = "SLEEPING"
    BUFFERING = "BUFFERING"
    PIPE = "PIPE"


class ProxyBase:
    def __init__(self, target_host: str, target_port: int, proxy_port: int, protocol: str = "tcp"):
        self.target_host = target_host
        self.target_port = target_port
        self.proxy_port = proxy_port
        self.protocol = protocol.lower()
        self.state = ProxyState.SLEEPING
        self.logger = logging.getLogger(f"proxy.{self.__class__.__name__}")
        self.on_wake_callback: Optional[Callable] = None
        self.running = False
    
    def set_wake_callback(self, callback: Callable):
        """Set callback function to invoke when server needs to wake"""
        self.on_wake_callback = callback
    
    async def run(self):
        """Main server loop - override for custom protocol handling"""
        if self.protocol == "tcp":
            await self._run_tcp()
        elif self.protocol == "udp":
            await self._run_udp()
        else:
            raise ValueError(f"Unsupported protocol: {self.protocol}")
    
    async def _run_tcp(self):
        """Standard TCP proxy server"""
        server = await asyncio.start_server(
            self._handle_tcp_client,
            '0.0.0.0',
            self.proxy_port
        )
        self.running = True
        self.logger.info(f"TCP Proxy listening on port {self.proxy_port}")
        
        async with server:
            await server.serve_forever()
    
    async def _run_udp(self):
        """Standard UDP proxy server"""
        transport, protocol = await asyncio.get_event_loop().create_datagram_endpoint(
            lambda: self._UDPProxyProtocol(self),
            local_addr=('0.0.0.0', self.proxy_port)
        )
        self.running = True
        self.logger.info(f"UDP Proxy listening on port {self.proxy_port}")
    
    async def _handle_tcp_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle TCP client connection"""
        client_addr = writer.get_extra_info('peername')
        self.logger.info(f"Client connected: {client_addr}")
        
        await self.on_connect(client_addr)
        
        try:
            if self.state == ProxyState.SLEEPING:
                await self._handle_sleeping_client(reader, writer)
            else:
                await self._pipe_connection(reader, writer)
        except Exception as e:
            self.logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _handle_sleeping_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle client while server is sleeping - buffer and wake"""
        self.logger.info("Server sleeping, buffering connection...")
        self.state = ProxyState.BUFFERING
        
        if self.on_wake_callback:
            await self.on_wake_callback()
        
        writer.write(b"Server is waking up...\n")
        await writer.drain()
        
        await asyncio.sleep(2)
        
        self.state = ProxyState.PIPE
        await self._pipe_connection(reader, writer)
    
    async def _pipe_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Pipe data between client and game server"""
        try:
            target_reader, target_writer = await asyncio.open_connection(
                self.target_host,
                self.target_port
            )
            
            async def forward(client_to_server: bool = True):
                try:
                    src_reader = reader if client_to_server else target_reader
                    dst_writer = target_writer if client_to_server else writer
                    
                    while True:
                        data = await src_reader.read(4096)
                        if not data:
                            break
                        
                        processed = await self.inspect_traffic(data, client_to_server)
                        if processed:
                            dst_writer.write(processed)
                            await dst_writer.drain()
                except Exception as e:
                    self.logger.error(f"Forward error: {e}")
                finally:
                    if client_to_server:
                        target_writer.close()
                        await target_writer.wait_closed()
                    else:
                        writer.close()
                        await writer.wait_closed()
            
            await asyncio.gather(
                forward(True),
                forward(False)
            )
        except Exception as e:
            self.logger.error(f"Pipe connection error: {e}")
    
    async def on_connect(self, client_addr: tuple):
        """
        Hook: Called when a player connects.
        Override to implement custom behavior (e.g., send wake signal).
        """
        self.logger.info(f"Connection from {client_addr}")
    
    async def inspect_traffic(self, data: bytes, client_to_server: bool) -> bytes:
        """
        Hook: Inspect packets passing through.
        Override to parse game-specific packets.
        Default: Pass-through.
        """
        return data
    
    async def stop(self):
        """Stop the proxy server"""
        self.running = False
        self.logger.info("Proxy stopped")
    
    class _UDPProxyProtocol(asyncio.DatagramProtocol):
        def __init__(self, proxy: 'ProxyBase'):
            self.proxy = proxy
            self.transport = None
        
        def connection_made(self, transport):
            self.transport = transport
        
        def datagram_received(self, data, addr):
            asyncio.create_task(self.proxy._handle_udp_datagram(data, addr))
        
        def error_received(self, exc):
            self.proxy.logger.error(f"UDP error: {exc}")
    
    async def _handle_udp_datagram(self, data: bytes, addr: tuple):
        """Handle incoming UDP datagram"""
        await self.on_connect(addr)
        
        processed = await self.inspect_traffic(data, True)
        
        if processed:
            loop = asyncio.get_event_loop()
            loop.create_datagram_endpoint(
                lambda: self._UDPReturnProtocol(addr, self.transport),
                remote_addr=(self.target_host, self.target_port)
            )
    
    class _UDPReturnProtocol(asyncio.DatagramProtocol):
        def __init__(self, client_addr, transport):
            self.client_addr = client_addr
            self.client_transport = transport
        
        def datagram_received(self, data, addr):
            self.client_transport.sendto(data, self.client_addr)
        
        def error_received(self, exc):
            logging.error(f"UDP return error: {exc}")
