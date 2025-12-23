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
    
    id: Optional[int] = Field(default=None, primary_key=True, description="Unique user identifier")
    email: str = Field(unique=True, index=True, description="User email address")
    provider: Provider = Field(default=Provider.GOOGLE, description="OAuth provider used for authentication")
    credits: float = Field(default=0.0, description="Available credits for server usage")
    is_admin: bool = Field(default=False, description="Admin privileges")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Account creation timestamp")
    
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
    icon_url: str = Field(default="/static/img/default_icon.png")
    wallpaper_url: str = Field(default="/static/img/default_wallpaper.jpg")
    
    servers: list["Server"] = Relationship(back_populates="game_image")


class Server(SQLModel, table=True):
    __tablename__ = "servers"
    
    id: Optional[int] = Field(default=None, primary_key=True, description="Unique server identifier")
    user_id: int = Field(foreign_key="users.id", description="Owner user ID")
    game_image_id: int = Field(foreign_key="game_images.id", description="Game image ID")
    
    friendly_name: str = Field(description="Human-readable server name")
    env_vars: dict = Field(sa_column=Column(JSON), default={}, description="Environment variables for game server")
    
    proxy_container_id: Optional[str] = Field(default=None, description="Docker container ID for sidecar proxy")
    game_container_id: Optional[str] = Field(default=None, description="Docker container ID for game server")
    public_port: Optional[int] = Field(default=None, description="Public port mapped by sidecar proxy")
    private_network_name: Optional[str] = Field(default=None, description="Docker network name")
    
    state: ServerState = Field(default=ServerState.SLEEPING, description="Current server state")
    auto_sleep: bool = Field(default=True, description="Enable auto-hibernation after idle period")
    gcs_backup_path: Optional[str] = Field(default=None, description="GCS path for server data backups")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Server creation timestamp")
    last_state_change: datetime = Field(default_factory=datetime.utcnow, description="Last state transition timestamp")
    
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
    friendly_name: str = Field(..., description="Human-readable server name", schema_extra={"example": "My Minecraft Survival"})
    game_image_id: int = Field(..., description="Game image ID", schema_extra={"example": 1})
    env_vars: Optional[dict] = Field(default=None, description="Environment variables for game server")
    auto_sleep: bool = Field(default=True, description="Enable auto-hibernation after 15 mins idle")


class ServerUpdate(SQLModel):
    friendly_name: Optional[str] = None
    env_vars: Optional[dict] = None
    auto_sleep: Optional[bool] = None


class WakeWebhook(SQLModel):
    server_id: int
    token: str
