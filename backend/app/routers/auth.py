from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from models import User
from database import get_session
from datetime import timedelta
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")

# OAuth SSO instances will be initialized in main.py and set here
google_sso = None
microsoft_sso = None


def set_sso_providers(google, microsoft):
    global google_sso, microsoft_sso
    google_sso = google
    microsoft_sso = microsoft


@router.get("/login", summary="Login Page")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/login/google", summary="Google OAuth Login")
async def google_login():
    if not google_sso:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    
    return await google_sso.get_login_redirect()


@router.get("/callback/google", summary="Google OAuth Callback")
async def google_callback(
    request: Request,
    response: Response,
    session: Session = Depends(get_session)
):
    if not google_sso:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    
    try:
        # Get user info from Google
        user_info = await google_sso.verify_and_process(request)
        
        email = user_info.email
        provider_id = user_info.id
        display_name = user_info.display_name
        avatar_url = user_info.picture
        
        # Find or create user
        user = session.exec(
            select(User).where(User.email == email)
        ).first()
        
        if user:
            # Update existing user
            user.display_name = display_name
            user.avatar_url = avatar_url
            if user.provider != "google":
                user.provider = "google"
                user.provider_id = provider_id
        else:
            # Create new user
            user = User(
                email=email,
                display_name=display_name,
                provider="google",
                provider_id=provider_id,
                avatar_url=avatar_url,
                credits=10.0  # Free starting credits
            )
            session.add(user)
        
        session.commit()
        session.refresh(user)
        
        # Create JWT token
        from services.auth import create_access_token
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(days=30)
        )
        
        # Set cookie and redirect
        redirect = RedirectResponse(url="/dashboard", status_code=303)
        redirect.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=30 * 24 * 60 * 60  # 30 days
        )
        return redirect
        
    except Exception as e:
        logger.error(f"Google OAuth error: {str(e)}")
        raise HTTPException(status_code=400, detail="Authentication failed")


@router.get("/login/microsoft", summary="Microsoft OAuth Login")
async def microsoft_login():
    if not microsoft_sso:
        raise HTTPException(status_code=503, detail="Microsoft OAuth not configured")
    
    return await microsoft_sso.get_login_redirect()


@router.get("/callback/microsoft", summary="Microsoft OAuth Callback")
async def microsoft_callback(
    request: Request,
    response: Response,
    session: Session = Depends(get_session)
):
    if not microsoft_sso:
        raise HTTPException(status_code=503, detail="Microsoft OAuth not configured")
    
    try:
        # Get user info from Microsoft
        user_info = await microsoft_sso.verify_and_process(request)
        
        email = user_info.email
        provider_id = user_info.id
        display_name = user_info.display_name
        avatar_url = user_info.picture
        
        # Find or create user
        user = session.exec(
            select(User).where(User.email == email)
        ).first()
        
        if user:
            # Update existing user
            user.display_name = display_name
            user.avatar_url = avatar_url
            if user.provider != "microsoft":
                user.provider = "microsoft"
                user.provider_id = provider_id
        else:
            # Create new user
            user = User(
                email=email,
                display_name=display_name,
                provider="microsoft",
                provider_id=provider_id,
                avatar_url=avatar_url,
                credits=10.0
            )
            session.add(user)
        
        session.commit()
        session.refresh(user)
        
        # Create JWT token
        from services.auth import create_access_token
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(days=30)
        )
        
        # Set cookie and redirect
        redirect = RedirectResponse(url="/dashboard", status_code=303)
        redirect.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=30 * 24 * 60 * 60
        )
        return redirect
        
    except Exception as e:
        logger.error(f"Microsoft OAuth error: {str(e)}")
        raise HTTPException(status_code=400, detail="Authentication failed")


@router.post("/dev-login", summary="Developer Instant Login")
async def dev_login(session: Session = Depends(get_session)):
    dev_email = "admin@gsp.dev"
    
    user = session.exec(
        select(User).where(User.email == dev_email)
    ).first()
    
    if not user:
        user = User(
            email=dev_email,
            display_name="Dev Admin",
            provider="dev",
            provider_id="dev_admin_001",
            avatar_url=None,
            credits=1000.0,
            is_admin=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    
    from services.auth import create_access_token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(days=30)
    )
    
    redirect = RedirectResponse(url="/dashboard", status_code=303)
    redirect.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=30 * 24 * 60 * 60
    )
    return redirect


@router.post("/logout", summary="Logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie("access_token")
    return response
