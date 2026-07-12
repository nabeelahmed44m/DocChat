"""Auth endpoints — register, login, get/update profile."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.config import Settings, get_settings
from app.services.storage.user_store import UserStore

router = APIRouter(prefix="/auth", tags=["auth"])


# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: str
    updated_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


# --------------------------------------------------------------------------- #
# Helpers / dependencies                                                       #
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def _get_user_store() -> UserStore:
    return UserStore(get_settings())


def _make_token(user_id: str, settings: Settings) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def current_user_id(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """FastAPI dependency — validates JWT and returns user_id."""
    token = ""
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired — please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _user_response(user) -> UserResponse:
    return UserResponse(
        id=user.id, email=user.email, name=user.name,
        created_at=user.created_at, updated_at=user.updated_at,
    )


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #

@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest, settings: Settings = Depends(get_settings)):
    store = _get_user_store()
    if store.get_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = store.create(email=body.email, name=body.name, hashed_password=hashed)
    return AuthResponse(token=_make_token(user.id, settings), user=_user_response(user))


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, settings: Settings = Depends(get_settings)):
    store = _get_user_store()
    user = store.get_by_email(body.email)
    if not user or not bcrypt.checkpw(body.password.encode(), user.hashed_password.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return AuthResponse(token=_make_token(user.id, settings), user=_user_response(user))


@router.get("/profile", response_model=UserResponse)
def get_profile(user_id: str = Depends(current_user_id)):
    user = _get_user_store().get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_response(user)


@router.put("/profile", response_model=UserResponse)
def update_profile(body: UpdateProfileRequest, user_id: str = Depends(current_user_id)):
    user = _get_user_store().update(user_id, name=body.name)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_response(user)


@router.delete("/profile", status_code=204)
def delete_account(user_id: str = Depends(current_user_id)):
    deleted = _get_user_store().delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
