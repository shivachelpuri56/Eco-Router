"""
Authentication router for Eco-Router.
Handles user registration, login (JWT generation), and logout.
Uses HTTPOnly cookies for security.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eco_router.config import settings
from eco_router.database import get_db
from eco_router.db_models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Schemas ───────────────────────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr

# ── Utilities ─────────────────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.auth_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.auth_secret, algorithm=settings.auth_algorithm)

def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="eco_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        max_age=settings.auth_token_expire_minutes * 60,
    )

def clear_auth_cookie(response: Response):
    response.delete_cookie(
        key="eco_token",
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
    )

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get("eco_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=[settings.auth_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse)
async def register(req: UserRegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Register a new user and set JWT cookie."""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = pwd_context.hash(req.password)
    new_user = User(
        name=req.name,
        email=req.email,
        hashed_password=hashed_password
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Auto-login
    token = create_access_token({"sub": new_user.id, "email": new_user.email})
    set_auth_cookie(response, token)
    
    return UserResponse(id=new_user.id, name=new_user.name, email=new_user.email)


@router.post("/login")
async def login(req: UserLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Authenticate user and set JWT cookie."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    
    if not user or not pwd_context.verify(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    token = create_access_token({"sub": user.id, "email": user.email})
    set_auth_cookie(response, token)
    
    return {"message": "Login successful", "user": {"name": user.name, "email": user.email}}


@router.post("/logout")
async def logout(response: Response):
    """Clear JWT cookie."""
    clear_auth_cookie(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return UserResponse(id=user.id, name=user.name, email=user.email)
