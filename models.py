from enum import Enum
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON
import pydantic


class ServerState(str, Enum):
    RUNNING = "RUNNING"
    SLEEPING = "SLEEPING"
    STARTING = "STARTING"
    STOPPING = "STOPPING"


class Provider(str, Enum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"


class TransactionType(str, Enum):
    DEPOSIT = "DEPOSIT"
    HOURLY_CHARGE = "HOURLY_CHARGE"


class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    provider: Provider = Field(default=Provider.GOOGLE)
    credits: float = Field(default=0.0)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    servers: list["Server"] = Relationship(back_populates="user")
    transactions: list["Transaction"] = Relationship(back_populates="user")


class GameImage(SQLModel, table=True):
    __tablename__ = "game_images"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    friendly_name: str = Field(unique=True)
    docker_image: str
    default_internal_port: int
    min_ram: str
    min_cpu: str
    protocol: str = Field(default="tcp")
    description: Optional[str] = None
    
    servers: list["Server"] = Relationship(back_populates="game_image")


class Server(SQLModel, table=True):
    __tablename__ = "servers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    game_image_id: int = Field(foreign_key="game_images.id")
    
    friendly_name: str
    env_vars: dict = Field(sa_column=Column(JSON), default={})
    
    proxy_container_id: Optional[str] = None
    game_container_id: Optional[str] = None
    public_port: Optional[int] = None
    private_network_name: Optional[str] = None
    
    state: ServerState = Field(default=ServerState.SLEEPING)
    auto_sleep: bool = Field(default=True)
    gcs_backup_path: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_state_change: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="servers")
    game_image: GameImage = Relationship(back_populates="servers")


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    amount: float
    type: TransactionType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    description: Optional[str] = None
    
    user: User = Relationship(back_populates="transactions")


class ServerCreate(SQLModel):
    friendly_name: str
    game_image_id: int
    env_vars: Optional[dict] = None
    auto_sleep: bool = True


class ServerUpdate(SQLModel):
    friendly_name: Optional[str] = None
    env_vars: Optional[dict] = None
    auto_sleep: Optional[bool] = None


class WakeWebhook(SQLModel):
    server_id: int
    token: str
