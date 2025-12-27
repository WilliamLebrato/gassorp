import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select
from models import Server, ServerState, User, Transaction, TransactionType
from services.node_client import NodeClient

logger = logging.getLogger(__name__)


class LifecycleManager:
    def __init__(self, node_client: NodeClient, db_session_factory):
        self.node_client = node_client
        self.get_session = db_session_factory
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._lifecycle_loop())
        logger.info("Lifecycle manager started")
    
    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Lifecycle manager stopped")
    
    async def _lifecycle_loop(self):
        while self._running:
            try:
                await self._check_idle_servers()
                await self._process_billing()
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in lifecycle loop: {e}")
                await asyncio.sleep(60)
    
    async def _check_idle_servers(self):
        with self.get_session() as session:
            running_servers = session.exec(
                select(Server).where(Server.state == ServerState.RUNNING)
            ).all()
            
            for server in running_servers:
                if not server.auto_sleep:
                    continue
                
                try:
                    stats = await self.node_client.get_server_stats(server)
                    
                    if stats['cpu_percent'] < 5.0:
                        idle_time = datetime.utcnow() - server.last_state_change
                        
                        if idle_time >= timedelta(minutes=15):
                            logger.info(f"Server {server.id} idle for 15+ minutes, hibernating")
                            if await self.node_client.hibernate_server(server):
                                server.state = ServerState.SLEEPING
                                server.last_state_change = datetime.utcnow()
                                session.add(server)
                                session.commit()
                except Exception as e:
                    logger.error(f"Error checking idle status for server {server.id}: {e}")
    
    async def _process_billing(self):
        with self.get_session() as session:
            running_servers = session.exec(
                select(Server).where(Server.state == ServerState.RUNNING)
            ).all()
            
            for server in running_servers:
                user = session.get(User, server.user_id)
                
                if user.credits <= 0:
                    logger.warning(f"User {user.id} has zero credits, hibernating server {server.id}")
                    await self.node_client.hibernate_server(server)
                    server.state = ServerState.SLEEPING
                    server.last_state_change = datetime.utcnow()
                    session.add(server)
                    session.commit()
                    continue
                
                charge_amount = 0.5
                
                if user.credits >= charge_amount:
                    user.credits -= charge_amount
                    
                    transaction = Transaction(
                        user_id=user.id,
                        amount=-charge_amount,
                        type=TransactionType.HOURLY_CHARGE,
                        description=f"Server {server.friendly_name} ({server.id}) hourly charge"
                    )
                    session.add(transaction)
                    session.add(user)
                    
                    logger.debug(f"Charged {charge_amount} credits from user {user.id} for server {server.id}")
                else:
                    logger.warning(f"User {user.id} insufficient credits, hibernating server {server.id}")
                    await self.node_client.hibernate_server(server)
                    server.state = ServerState.SLEEPING
                    server.last_state_change = datetime.utcnow()
                    session.add(server)
            
            session.commit()
    
    async def wake_on_webhook(self, server_id: int, token: str) -> bool:
        if token != self.node_client.secret:
            logger.warning(f"Invalid webhook token for server {server_id}")
            return False
        
        with self.get_session() as session:
            server = session.get(Server, server_id)
            if not server:
                logger.error(f"Server {server_id} not found")
                return False
            
            user = session.get(User, server.user_id)
            if user.credits <= 0:
                logger.warning(f"User {user.id} has insufficient credits, denying wake")
                return False
            
            logger.info(f"Webhook wake request for server {server_id}")
            if await self.node_client.wake_server(server):
                server.state = ServerState.RUNNING
                server.last_state_change = datetime.utcnow()
                session.add(server)
                session.commit()
                return True
            
            return False
    
    async def add_credits(self, user_id: int, amount: float, description: str = "Deposit") -> bool:
        with self.get_session() as session:
            user = session.get(User, user_id)
            if not user:
                return False
            
            user.credits += amount
            
            transaction = Transaction(
                user_id=user_id,
                amount=amount,
                type=TransactionType.DEPOSIT,
                description=description
            )
            session.add(transaction)
            session.add(user)
            session.commit()
            
            logger.info(f"Added {amount} credits to user {user_id}")
            return True
