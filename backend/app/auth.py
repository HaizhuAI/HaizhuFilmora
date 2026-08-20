"""Auth helpers: admin session (JWT cookie) + API key (Bearer)."""
from __future__ import annotations

import time
from typing import Optional

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .db import is_valid_key

ALGO = "HS256"

bearer_scheme = HTTPBearer(auto_error=False)


def create_session_token() -> str:
    payload = {"sub": "admin", "iat": int(time.time()), "exp": int(time.time()) + settings.SESSION_TTL_HOURS * 3600}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGO)


def decode_session_token(token: str) -> bool:
    try:
        jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])
        return True
    except Exception:
        return False


def require_admin(cookie: Optional[str] = Cookie(None, alias=settings.SESSION_COOKIE)) -> None:
    if not cookie or not decode_session_token(cookie):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要管理员登录")
    return None


def require_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 Bearer token")
    if not is_valid_key(credentials.credentials):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 API key")
    return credentials.credentials


def optional_admin(cookie: Optional[str] = Cookie(None, alias=settings.SESSION_COOKIE)) -> bool:
    return bool(cookie and decode_session_token(cookie))
