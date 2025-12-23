from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from models import User, Provider
from services.auth import MockOAuthHandler, create_access_token
from database import get_session
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", summary="Login Page", description="Render the login page with OAuth options and dev login button.")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/mock-login", summary="Mock OAuth Login", description="Authenticate user with email using mock OAuth flow.")
async def mock_login(
    request: Request,
    email: str = Form(...),
    session: Session = Depends(get_session)
):
    user = MockOAuthHandler.authenticate_mock_user(session, email, "google")
    if not user:
        raise HTTPException(status_code=400, detail="Failed to create user")
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(days=30)
    )
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=1800
    )
    return response


@router.get("/mock/{provider}")
async def mock_oauth_callback(
    provider: str,
    state: str,
    session: Session = Depends(get_session)
):
    mock_email = f"user_{state}@{provider}.com"
    user = MockOAuthHandler.authenticate_mock_user(session, mock_email, provider)
    if not user:
        raise HTTPException(status_code=400, detail="Failed to create user")
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(days=30)
    )
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=1800
    )
    return response


@router.post("/dev-login", summary="Developer Instant Login", description="Instant login for development. Creates or retrieves admin@gsp.dev user with 1000 credits and redirects to dashboard.")
async def dev_login(session: Session = Depends(get_session)):
    dev_email = "admin@gsp.dev"
    
    user = session.exec(
        select(User).where(User.email == dev_email)
    ).first()
    
    if not user:
        user = User(
            email=dev_email,
            provider=Provider.GOOGLE,
            is_admin=True,
            credits=1000.0
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(days=30)
    )
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=1800
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login")
    response.delete_cookie("access_token")
    return response
