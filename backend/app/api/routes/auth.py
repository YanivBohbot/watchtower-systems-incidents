"""Sign-in and the current user's profile."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.dependencies import current_user, get_sessions, get_settings
from app.api.schemas import Login, public
from app.core.config import Settings
from app.core.security import token_for, verify_password
from app.database.models import User

router = APIRouter()


@router.post("/api/auth/login")
def login(body: Login, cfg: Settings = Depends(get_settings), sessions=Depends(get_sessions)):
    with sessions() as db:
        user = db.scalar(select(User).where(User.email == body.email.lower()))
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(401, "Invalid credentials")
        return {"access_token": token_for(user.id, cfg.jwt_secret.get_secret_value()), "user": public(user)}


@router.get("/api/me")
def me(user: User = Depends(current_user)):
    return public(user)
