"""Video editing endpoints: ops, concat, export, filters/stickers/transitions."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_admin
from ..config import settings
from ..db import get_media
from ..engine.ffmpeg import (FFmpegError, apply_ops, concat_videos, extract_audio,
                             make_gif, out_path, probe_media)
from ..engine.filters import filter_list, sticker_list, transition_list
from ..jobs import manager
from ..models import EditRequest

router = APIRouter(prefix="/api/edit", tags=["edit"])


def _media_path(media_id: str) -> str:
    m = get_media(media_id)
    if not m or not Path(m["path"]).exists():
        raise HTTPException(status_code=404, detail="媒体不存在")
    return m["path"]


@router.get("/filters")
def filters(_=Depends(require_admin)) -> dict:
    return {"items": filter_list()}


@router.get("/stickers")
def stickers(_=Depends(require_admin)) -> dict:
    return {"items": sticker_list()}


@router.get("/transitions")
def transitions(_=Depends(require_admin)) -> dict:
    return {"items": transition_list()}


@router.get("/probe/{media_id}")
def probe(media_id: str, _=Depends(require_admin)) -> dict:
    try:
        return probe_media(_media_path(media_id))
    except FFmpegError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/apply")
def apply(body: EditRequest, _=Depends(require_admin)) -> dict:
    src = _media_path(body.media_id)
    ext = ".gif" if body.export.get("format") == "gif" else ".mp4"
    out = out_path(f"edit_{int(time.time())}", ext)
    try:
        if ext == ".gif":
            make_gif(src, out,
                     start=float(body.export.get("start", 0)),
                     duration=float(body.export.get("duration", 3)),
                     fps=int(body.export.get("fps", 12)),
                     width=int(body.export.get("width", 480)))
            return {"url": f"/exports/{out.name}", "file": str(out), "format": "gif"}
        apply_ops(src, body.ops, out, body.export)
        return {"url": f"/exports/{out.name}", "file": str(out)}
    except FFmpegError as exc:
        out.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/apply_async")
async def apply_async(body: EditRequest, _=Depends(require_admin)) -> dict:
    src = _media_path(body.media_id)
    job_id = await manager.enqueue("edit", {"media_id": body.media_id, "src": src, "ops": body.ops, "export": body.export}, _job_apply)
    return {"job_id": job_id}


def _job_apply(payload: dict, report) -> dict:
    ext = ".gif" if payload.get("export", {}).get("format") == "gif" else ".mp4"
    out = out_path(f"edit_{int(time.time())}", ext)
    report(0.1, "开始处理…")
    if ext == ".gif":
        e = payload["export"]
        make_gif(payload["src"], out,
                 start=float(e.get("start", 0)), duration=float(e.get("duration", 3)),
                 fps=int(e.get("fps", 12)), width=int(e.get("width", 480)),
                 progress_cb=lambda p: report(0.1 + 0.8 * p))
        return {"url": f"/exports/{out.name}", "file": str(out), "format": "gif"}
    apply_ops(payload["src"], payload.get("ops", []), out, payload.get("export", {}),
              progress_cb=lambda p: report(0.1 + 0.8 * p, "编码中…"))
    return {"url": f"/exports/{out.name}", "file": str(out)}


@router.post("/concat")
async def concat(media_ids: list[str], _=Depends(require_admin)) -> dict:
    paths = [_media_path(mid) for mid in media_ids]
    if not paths:
        raise HTTPException(status_code=400, detail="至少需要一个片段")
    out = out_path(f"concat_{int(time.time())}", "mp4")
    job_id = await manager.enqueue("concat", {"paths": paths}, _job_concat)
    return {"job_id": job_id, "media_ids": media_ids}


def _job_concat(payload: dict, report) -> dict:
    report(0.1, "合并中…")
    out = out_path(f"concat_{int(time.time())}", "mp4")
    concat_videos(payload["paths"], out, progress_cb=lambda p: report(0.1 + 0.8 * p))
    return {"url": f"/exports/{out.name}", "file": str(out)}


@router.post("/audio")
def audio(media_id: str, _=Depends(require_admin)) -> dict:
    src = _media_path(media_id)
    out = out_path(f"audio_{int(time.time())}", "mp3")
    try:
        extract_audio(src, out)
        return {"url": f"/exports/{out.name}", "file": str(out)}
    except FFmpegError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/gif")
def gif(media_id: str, start: float = 0, duration: float = 3, fps: int = 12, width: int = 480,
        _=Depends(require_admin)) -> dict:
    src = _media_path(media_id)
    out = out_path(f"gif_{int(time.time())}", "gif")
    try:
        make_gif(src, out, start=start, duration=duration, fps=fps, width=width)
        return {"url": f"/exports/{out.name}", "file": str(out)}
    except FFmpegError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
