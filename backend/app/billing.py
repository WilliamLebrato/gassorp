import asyncio
import logging
from datetime import datetime
from sqlmodel import Session, select
from .models import User, Server, Transaction, TransactionType
from .database import get_session
from typing import Optional


logger = logging.getLogger(__name__)

# Billing configuration
CREDITS_PER_MINUTE = 0.1  # 0.1 credits per minute (6 credits/hour)
BILLING_INTERVAL_SECONDS = 60  # Run every 60 seconds


async def process_billing_cycle():
    """
    Process billing for all running servers.
    - Deducts credits from users for each running server
    - Stops servers when users run out of credits
    - Creates transaction records
    """
    logger.info("Starting billing cycle")
    
    session_gen = get_session()
    session: Session = next(session_gen)
    
    try:
        # Get all running servers
        running_servers = session.exec(
            select(Server).where(Server.state == "RUNNING")
        ).all()
        
        if not running_servers:
            logger.info("No running servers to bill")
            return
        
        logger.info(f"Billing {len(running_servers)} running servers")
        
        # Import lifecycle manager if available
        from .main import lifecycle_manager, docker_manager
        
        for server in running_servers:
            try:
                # Get the server owner
                user = session.get(User, server.user_id)
                if not user:
                    logger.error(f"Server {server.id} has no valid user")
                    continue
                
                # Calculate cost for this billing period
                cost = CREDITS_PER_MINUTE
                
                # Check if user has enough credits
                if user.credits >= cost:
                    # Deduct credits
                    user.credits -= cost
                    
                    # Create transaction record
                    transaction = Transaction(
                        user_id=user.id,
                        type=TransactionType.HOURLY_CHARGE,
                        amount=-cost,
                        description=f"Server usage: {server.friendly_name} ({server.game_image.friendly_name})",
                        timestamp=datetime.utcnow()
                    )
                    session.add(transaction)
                    
                    logger.debug(f"Billed user {user.email} {cost} credits for server {server.id}")
                    
                else:
                    # User ran out of credits - stop the server
                    logger.warning(f"User {user.email} ran out of credits. Stopping server {server.id}")
                    
                    # Stop the server
                    if docker_manager:
                        try:
                            docker_manager.hibernate(server.id)
                            server.state = "SLEEPING"
                        except Exception as e:
                            logger.error(f"Failed to stop server {server.id}: {e}")
                    
                    # Create transaction for 0 balance
                    transaction = Transaction(
                        user_id=user.id,
                        type=TransactionType.HOURLY_CHARGE,
                        amount=-user.credits,  # Deduct remaining
                        description=f"Server stopped - out of credits: {server.friendly_name}",
                        timestamp=datetime.utcnow()
                    )
                    session.add(transaction)
                    
                    user.credits = 0
            
            except Exception as e:
                logger.error(f"Error billing server {server.id}: {e}")
        
        # Commit all changes
        session.commit()
        logger.info("Billing cycle completed successfully")
        
    except Exception as e:
        logger.error(f"Billing cycle failed: {e}")
        session.rollback()
    finally:
        session.close()


async def billing_daemon():
    """
    Background task that runs the billing cycle on an interval.
    This should be started when the application starts.
    """
    logger.info("Billing daemon started")
    
    while True:
        try:
            await process_billing_cycle()
        except Exception as e:
            logger.error(f"Billing daemon error: {e}")
        
        # Wait for next billing cycle
        await asyncio.sleep(BILLING_INTERVAL_SECONDS)


def get_user_balance(session: Session, user_id: int) -> float:
    """Get current credit balance for a user"""
    user = session.get(User, user_id)
    return user.credits if user else 0.0


def estimate_server_cost(minutes: int) -> float:
    """Estimate cost for running a server for a given time"""
    return minutes * CREDITS_PER_MINUTE


async def check_user_can_afford_server(session: Session, user_id: int, estimated_minutes: int = 60) -> bool:
    """Check if user has enough credits to run a server"""
    user = session.get(User, user_id)
    if not user:
        return False
    
    estimated_cost = estimate_server_cost(estimated_minutes)
    return user.credits >= estimated_cost
