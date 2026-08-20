"""Admin auth endpoints (WebUI session)."""
from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Response

from ..auth import create_session_token, decode_session_token, optional_admin
from ..config import settings
from ..models import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response) -> LoginResponse:
    if body.password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")
    token = create_session_token()
    response.set_cookie(
        settings.SESSION_COOKIE, token,
        httponly=True, samesite="lax", max_age=settings.SESSION_TTL_HOURS * 3600,
        path="/",
    )
    return LoginResponse(ok=True, message="登录成功")


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(settings.SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(cookie: str | None = Cookie(None, alias=settings.SESSION_COOKIE)) -> dict:
    return {"authed": bool(cookie and decode_session_token(cookie))}
