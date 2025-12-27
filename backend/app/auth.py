from typing import Optional
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlmodel import Session, select
from models import User, Provider
import secrets

SECRET_KEY = "your-secret-key-change-this"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


mock_providers_db = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token"
    },
    "microsoft": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    }
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), session=None) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = session.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


class MockOAuthHandler:
    
    @staticmethod
    def generate_mock_state() -> str:
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def create_mock_user(session: Session, email: str, provider: Provider = Provider.GOOGLE) -> User:
        existing_user = session.exec(
            select(User).where(User.email == email)
        ).first()
        
        if existing_user:
            return existing_user
        
        new_user = User(
            email=email,
            provider=provider,
            credits=10.0,
            is_admin=False
        )
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return new_user
    
    @staticmethod
    def authenticate_mock_user(session: Session, email: str, provider: str = "google") -> Optional[User]:
        try:
            provider_enum = Provider.GOOGLE if provider.lower() == "google" else Provider.MICROSOFT
            user = MockOAuthHandler.create_mock_user(session, email, provider_enum)
            return user
        except Exception as e:
            return None
    
    @staticmethod
    def create_login_url(provider: str = "google") -> str:
        state = MockOAuthHandler.generate_mock_state()
        return f"/auth/mock/{provider}?state={state}"
