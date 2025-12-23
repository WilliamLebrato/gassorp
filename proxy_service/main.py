import asyncio
import os
import logging
from aiohttp import ClientSession, ClientError
import socket
import struct

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TARGET_HOST = os.getenv("TARGET_HOST", "localhost")
TARGET_PORT = int(os.getenv("TARGET_PORT", "25565"))
BACKEND_WEBHOOK_URL = os.getenv("BACKEND_WEBHOOK_URL")
SERVER_ID = os.getenv("SERVER_ID")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
PROTOCOL = os.getenv("PROTOCOL", "tcp").upper()
LISTEN_PORT = int(os.getenv("LISTEN_PORT", "25565"))
HOLD_TIMEOUT = int(os.getenv("HOLD_TIMEOUT", "60"))
RETRY_INTERVAL = int(os.getenv("RETRY_INTERVAL", "2"))

if not all([BACKEND_WEBHOOK_URL, SERVER_ID, WEBHOOK_TOKEN]):
    raise ValueError("Missing required environment variables")


async def send_wake_signal():
    logger.info(f"Sending wake signal for server {SERVER_ID}")
    try:
        async with ClientSession() as session:
            payload = {
                "server_id": int(SERVER_ID),
                "token": WEBHOOK_TOKEN
            }
            async with session.post(BACKEND_WEBHOOK_URL, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    logger.info("Wake signal sent successfully")
                    return True
                else:
                    logger.error(f"Wake signal failed: {resp.status}")
                    return False
    except ClientError as e:
        logger.error(f"Failed to send wake signal: {e}")
        return False


async def check_target_reachable(host: str, port: int) -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=2.0
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
        return False


async def relay_tcp_data(client_reader, client_writer, target_reader, target_writer):
    async def forward(reader, writer):
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception as e:
            logger.error(f"Forward error: {e}")
        finally:
            writer.close()
    
    try:
        await asyncio.gather(
            forward(client_reader, target_writer),
            forward(target_reader, client_writer)
        )
    except Exception as e:
        logger.error(f"Relay error: {e}")
    finally:
        client_writer.close()
        target_writer.close()


async def handle_tcp_client(client_reader, client_writer, peer_addr):
    logger.info(f"New TCP connection from {peer_addr}")
    
    target_reachable = await check_target_reachable(TARGET_HOST, TARGET_PORT)
    
    if not target_reachable:
        logger.info(f"Target unreachable, initiating wake sequence")
        await send_wake_signal()
        
        logger.info("Entering hold mode - keeping client connection open")
        start_time = asyncio.get_event_loop().time()
        buffer = bytearray()
        
        try:
            client_writer.set_tcp_nodelay(False)
            
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= HOLD_TIMEOUT:
                    logger.warning("Hold timeout - target did not come online")
                    client_writer.close()
                    await client_writer.wait_closed()
                    return
                
                try:
                    data = await asyncio.wait_for(
                        client_reader.read(8192),
                        timeout=RETRY_INTERVAL
                    )
                    if data:
                        buffer.extend(data)
                        logger.debug(f"Buffered {len(data)} bytes from client")
                except asyncio.TimeoutError:
                    pass
                
                if await check_target_reachable(TARGET_HOST, TARGET_PORT):
                    logger.info("Target is now reachable - flushing buffer and bridging")
                    break
                
                logger.debug(f"Target still unreachable, waiting... ({elapsed:.1f}s elapsed)")
            
            target_reader, target_writer = await asyncio.open_connection(
                TARGET_HOST, TARGET_PORT
            )
            
            if buffer:
                logger.info(f"Flushing {len(buffer)} buffered bytes")
                target_writer.write(buffer)
                await target_writer.drain()
            
            await relay_tcp_data(client_reader, client_writer, target_reader, target_writer)
            
        except Exception as e:
            logger.error(f"Error during hold/bridge: {e}")
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except:
                pass
    else:
        logger.info("Target reachable - direct bridging")
        try:
            target_reader, target_writer = await asyncio.open_connection(
                TARGET_HOST, TARGET_PORT
            )
            await relay_tcp_data(client_reader, client_writer, target_reader, target_writer)
        except Exception as e:
            logger.error(f"Direct bridge error: {e}")
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except:
                pass


class UDPRelay:
    def __init__(self, client_addr, transport):
        self.client_addr = client_addr
        self.transport = transport
        self.target_transport = None
        self.buffer = []
    
    async def send_wake_and_hold(self):
        logger.info(f"UDP: Target unreachable, initiating wake for {self.client_addr}")
        await send_wake_signal()
        
        start_time = asyncio.get_event_loop().time()
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= HOLD_TIMEOUT:
                logger.warning("UDP hold timeout")
                return
            
            if await check_target_reachable(TARGET_HOST, TARGET_PORT):
                logger.info("UDP target reachable")
                break
            
            await asyncio.sleep(RETRY_INTERVAL)
        
        self.flush_buffer()
    
    def flush_buffer(self):
        if not self.target_transport:
            loop = asyncio.get_event_loop()
            
            class TargetProtocol:
                def __init__(self, relay, client_addr):
                    self.relay = relay
                    self.client_addr = client_addr
                
                def connection_made(self, transport):
                    self.relay.target_transport = transport
                    for data in self.relay.buffer:
                        transport.sendto(data, (TARGET_HOST, TARGET_PORT))
                    self.relay.buffer.clear()
                
                def datagram_received(self, data, addr):
                    self.relay.transport.sendto(data, self.client_addr)
                
                def error_received(self, exc):
                    logger.error(f"UDP target error: {exc}")
                
                def connection_lost(self, exc):
                    logger.info("UDP target connection lost")
            
            protocol = TargetProtocol(self, self.client_addr)
            loop.create_task(
                loop.create_datagram_endpoint(
                    lambda: protocol,
                    remote_addr=(TARGET_HOST, TARGET_PORT)
                )
            )


async def handle_udp_datagram(data, addr, protocol):
    if addr not in protocol.relays:
        protocol.relays[addr] = UDPRelay(addr, protocol.transport)
    
    relay = protocol.relays[addr]
    
    if relay.target_transport is None:
        target_reachable = await check_target_reachable(TARGET_HOST, TARGET_PORT)
        if not target_reachable:
            relay.buffer.append(data)
            if len(relay.buffer) == 1:
                asyncio.create_task(relay.send_wake_and_hold())
        else:
            relay.flush_buffer()
            relay.target_transport.sendto(data, (TARGET_HOST, TARGET_PORT))
    else:
        relay.target_transport.sendto(data, (TARGET_HOST, TARGET_PORT))


class UDPProxyProtocol:
    def __init__(self):
        self.relays = {}
        self.transport = None
    
    def connection_made(self, transport):
        self.transport = transport
        logger.info(f"UDP proxy listening on port {LISTEN_PORT}")
    
    def datagram_received(self, data, addr):
        asyncio.create_task(handle_udp_datagram(data, addr, self))
    
    def error_received(self, exc):
        logger.error(f"UDP proxy error: {exc}")


async def start_tcp_server():
    server = await asyncio.start_server(
        lambda r, w: asyncio.create_task(handle_tcp_client(r, w, w.get_extra_info('peername'))),
        '0.0.0.0',
        LISTEN_PORT
    )
    logger.info(f"TCP proxy listening on 0.0.0.0:{LISTEN_PORT}")
    async with server:
        await server.serve_forever()


async def start_udp_server():
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UDPProxyProtocol(),
        local_addr=('0.0.0.0', LISTEN_PORT)
    )
    logger.info(f"UDP proxy listening on 0.0.0.0:{LISTEN_PORT}")
    
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        transport.close()


async def main():
    logger.info(f"Proxy starting - Protocol: {PROTOCOL}, Target: {TARGET_HOST}:{TARGET_PORT}")
    
    if PROTOCOL == "udp":
        await start_udp_server()
    else:
        await start_tcp_server()


if __name__ == "__main__":
    asyncio.run(main())
