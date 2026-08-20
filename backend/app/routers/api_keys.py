"""API key management (for OpenAI-compatible endpoints)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_admin
from ..db import add_api_key, list_api_keys, revoke_api_key
from ..models import KeyCreate, KeyOut

router = APIRouter(prefix="/api/keys", tags=["keys"])


@router.get("")
def list_keys(_=Depends(require_admin)) -> dict:
    return {"items": list_api_keys()}


@router.post("", response_model=KeyOut)
def create_key(body: KeyCreate, _=Depends(require_admin)) -> KeyOut:
    key = add_api_key(body.name or "default")
    keys = list_api_keys()
    rec = next((k for k in keys if k["key"] == key), {"key": key, "name": body.name, "enabled": 1, "created_at": 0})
    return KeyOut(**rec)


@router.delete("/{key}")
def delete_key(key: str, _=Depends(require_admin)) -> dict:
    if not revoke_api_key(key):
        raise HTTPException(status_code=404, detail="key 不存在")
    return {"ok": True}
