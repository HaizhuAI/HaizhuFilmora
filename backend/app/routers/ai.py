"""AI endpoints: subtitles, remove, autoclip, text-to-video."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_admin
from ..config import settings
from ..db import get_media
from ..engine import remove_bg, subtitles as sub_engine, auto_clip as ac_engine, t2v as t2v_engine
from ..engine.ffmpeg import FFmpegError, out_path
from ..jobs import manager
from ..models import AutoClipRequest, RemoveRequest, SubtitleRequest, T2VRequest

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _media_path(media_id: str) -> str:
    m = get_media(media_id)
    if not m or not Path(m["path"]).exists():
        raise HTTPException(status_code=404, detail="媒体不存在")
    return m["path"]


def _media_kind(media_id: str) -> str:
    m = get_media(media_id)
    return (m or {}).get("kind", "video")


# ---------- smart subtitles ----------
@router.post("/subtitles")
async def subtitles(body: SubtitleRequest, _=Depends(require_admin)) -> dict:
    src = _media_path(body.media_id)
    job_id = await manager.enqueue("subtitles", {
        "media_id": body.media_id, "src": src, "lang": body.lang,
        "model": body.model, "burn_in": body.burn_in, "style": body.style,
    }, _job_subtitles)
    return {"job_id": job_id}


def _job_subtitles(payload: dict, report) -> dict:
    report(0.05, "转写中…")
    segments = sub_engine.transcribe(payload["src"], lang=payload.get("lang", "auto"),
                                     model=payload.get("model", "small"), report=report)
    srt_path = out_path(f"sub_{int(time.time())}", "srt", subdir="jobs")
    sub_engine.make_srt(segments, srt_path)
    result = {"segments": segments, "srt_url": f"/jobs/{srt_path.name}", "srt_file": str(srt_path)}
    if payload.get("burn_in"):
        report(0.85, "烧录字幕…")
        out = out_path(f"subbed_{int(time.time())}", "mp4")
        sub_engine.burn_subtitles(payload["src"], str(srt_path), out, payload.get("style"), report)
        result["video_url"] = f"/exports/{out.name}"
        result["video_file"] = str(out)
    return result


# ---------- AI remove ----------
@router.post("/remove")
async def remove(body: RemoveRequest, _=Depends(require_admin)) -> dict:
    src = _media_path(body.media_id)
    kind = _media_kind(body.media_id)
    job_id = await manager.enqueue("remove", {
        "media_id": body.media_id, "src": src, "mode": body.mode,
        "mask": body.mask, "kind": kind, "provider": body.provider,
    }, _job_remove)
    return {"job_id": job_id}


def _job_remove(payload: dict, report) -> dict:
    report(0.1, "AI 消除开始…")
    mode = payload.get("mode", "background")
    kind = payload.get("kind", "video")
    if mode == "object":
        out = out_path(f"remove_obj_{int(time.time())}", "png" if kind != "video" else "mp4")
        if kind == "video":
            raise HTTPException(status_code=400, detail="视频物体消除需先抽帧定位，请先用图片模式")
        remove_bg.remove_object_image(payload["src"], str(out), payload.get("mask"), report)
        return {"url": f"/exports/{out.name}", "file": str(out), "mode": "object"}
    if kind == "video":
        out = out_path(f"remove_bg_{int(time.time())}", "webm")
        remove_bg.remove_background_video(payload["src"], str(out), bg_color=None, report=report)
        return {"url": f"/exports/{out.name}", "file": str(out), "mode": "background", "format": "webm(透明)"}
    out = out_path(f"remove_bg_{int(time.time())}", "png")
    remove_bg.remove_bg_image(payload["src"], str(out), bg_color=None, report=report)
    return {"url": f"/exports/{out.name}", "file": str(out), "mode": "background"}


# ---------- auto clip ----------
@router.post("/autoclip")
async def autoclip(body: AutoClipRequest, _=Depends(require_admin)) -> dict:
    src = _media_path(body.media_id)
    job_id = await manager.enqueue("autoclip", {
        "media_id": body.media_id, "src": src, "mode": body.mode,
        "max_clips": body.max_clips, "min_clip_seconds": body.min_clip_seconds,
    }, _job_autoclip)
    return {"job_id": job_id}


def _job_autoclip(payload: dict, report) -> dict:
    report(0.1, "场景分析…")
    return ac_engine.auto_clip(payload["src"], mode=payload.get("mode", "highlights"),
                               max_clips=int(payload.get("max_clips", 5)),
                               min_clip_seconds=float(payload.get("min_clip_seconds", 1.0)),
                               report=report)


# ---------- text to video ----------
@router.post("/t2v")
async def t2v(body: T2VRequest, _=Depends(require_admin)) -> dict:
    job_id = await manager.enqueue("t2v", body.model_dump(), _job_t2v)
    return {"job_id": job_id}


def _job_t2v(payload: dict, report) -> dict:
    report(0.02, "排队渲染…")
    return t2v_engine.generate(
        payload.get("prompt", ""), duration=float(payload.get("duration", 5)),
        size=payload.get("size", "1280x720"), orientation=payload.get("orientation", "16:9"),
        voiceover=payload.get("voiceover"), lang=payload.get("lang", "auto"),
        provider=payload.get("provider", "local"), report=report)


@router.get("/jobs/recent")
def recent_jobs(limit: int = 40, _=Depends(require_admin)) -> dict:
    from ..db import list_jobs
    return {"items": list_jobs(limit)}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, _=Depends(require_admin)) -> dict:
    from ..db import get_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job
