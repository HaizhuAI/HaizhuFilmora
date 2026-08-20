"""Media library: upload, list, preview, delete."""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..auth import require_admin
from ..config import settings
from ..db import delete_media, get_media, insert_media, list_media
from ..engine.ffmpeg import make_media_record, make_thumbnail, probe_media, safe_name

router = APIRouter(prefix="/api/media", tags=["media"])

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".3gp", ".flv", ".wmv", ".ts"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
AUDIO_EXT = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"}


def _kind_for(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    return "file"


@router.post("/upload")
def upload(file: UploadFile = File(...), _=Depends(require_admin)) -> dict:
    media_id = "m_" + uuid.uuid4().hex[:12]
    name = safe_name(file.filename or "media")
    kind = _kind_for(name)
    if kind == "file":
        raise HTTPException(status_code=400, detail=f"不支持的格式: {file.filename}")
    dest = settings.UPLOAD_DIR / f"{media_id}_{name}"
    size = 0
    with open(dest, "wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            out.write(chunk)
    if size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail="文件超过大小限制")
    try:
        rec = make_media_record(str(dest), name, media_id, kind=kind, mime=file.content_type or "")
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"无法解析媒体: {exc}") from exc
    insert_media(rec)
    rec["url"] = f"/api/media/{media_id}/file"
    return rec


@router.get("")
def list_all(_=Depends(require_admin)) -> dict:
    items = []
    for m in list_media():
        m["url"] = f"/api/media/{m['id']}/file"
        items.append(m)
    return {"items": items, "total": len(items)}


@router.get("/{media_id}")
def get(media_id: str, _=Depends(require_admin)) -> dict:
    m = get_media(media_id)
    if not m:
        raise HTTPException(status_code=404, detail="媒体不存在")
    m["url"] = f"/api/media/{media_id}/file"
    return m


@router.get("/{media_id}/file")
def file(media_id: str, _=Depends(require_admin)) -> FileResponse:
    m = get_media(media_id)
    if not m or not Path(m["path"]).exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(m["path"], filename=m["name"])


@router.get("/{media_id}/thumbnail")
def thumbnail(media_id: str, _=Depends(require_admin)) -> FileResponse:
    m = get_media(media_id)
    if not m or not Path(m["path"]).exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    thumb = settings.JOB_DIR / f"{media_id}_thumb.jpg"
    if not thumb.exists():
        try:
            make_thumbnail(m["path"], thumb)
        except Exception:
            raise HTTPException(status_code=500, detail="生成缩略图失败")
    return FileResponse(thumb, media_type="image/jpeg")


@router.delete("/{media_id}")
def remove(media_id: str, _=Depends(require_admin)) -> dict:
    m = get_media(media_id)
    if not m:
        raise HTTPException(status_code=404, detail="媒体不存在")
    Path(m["path"]).unlink(missing_ok=True)
    delete_media(media_id)
    return {"ok": True}
