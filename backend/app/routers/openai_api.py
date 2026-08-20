"""OpenAI-compatible video API.

Auth:  Authorization: Bearer <api_key>
Endpoints:
  GET  /v1/models                     -> model list
  POST /v1/videos/generations         -> text-to-video (async job)
  POST /v1/videos/edits               -> video modification (async job)
  GET  /v1/videos/{job_id}            -> job status / result (OpenAI format)
  POST /v1/files                      -> upload media (multipart)
  GET  /v1/files/{file_id}            -> file metadata

Jobs are async: generation returns 202 with {id,status,created_at} then clients
poll /v1/videos/{id} until status=completed with output.data[0].url / b64_json.
"""
from __future__ import annotations

import base64
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..auth import require_api_key
from ..config import settings
from ..db import create_job, get_job, get_media, insert_media, update_job
from ..engine.ffmpeg import FFmpegError, apply_ops, make_media_record, out_path, probe_media, safe_name
from ..engine import remove_bg, subtitles as sub_engine, t2v as t2v_engine
from ..jobs import manager
from ..models import OpenAIVideoEditRequest, OpenAIVideoGenRequest

router = APIRouter(prefix="/v1", tags=["openai"])

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".3gp"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _err(message: str, code: str = "invalid_request_error", status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": {"message": message, "type": code, "code": code}})


def _now() -> int:
    return int(time.time())


@router.get("/models")
def models(_: str = Depends(require_api_key)) -> dict:
    return {
        "object": "list",
        "data": [
            {"id": settings.T2V_MODEL, "object": "model", "created": _now(),
             "owned_by": "filmora-webui", "capabilities": ["video_generation"]},
            {"id": settings.EDIT_MODEL, "object": "model", "created": _now(),
             "owned_by": "filmora-webui", "capabilities": ["video_edit", "video_modification"]},
            {"id": "filmora-smart-subtitle", "object": "model", "created": _now(),
             "owned_by": "filmora-webui", "capabilities": ["subtitle"]},
            {"id": "filmora-ai-remove", "object": "model", "created": _now(),
             "owned_by": "filmora-webui", "capabilities": ["video_edit"]},
            {"id": "filmora-auto-clip", "object": "model", "created": _now(),
             "owned_by": "filmora-webui", "capabilities": ["video_edit"]},
        ],
    }


# ------------------------------------------------------------------ generation
@router.post("/videos/generations", status_code=202)
async def video_generations(body: OpenAIVideoGenRequest, _: str = Depends(require_api_key)) -> dict:
    if not body.prompt.strip():
        raise _err("prompt 不能为空")
    if body.n and body.n != 1:
        raise _err("n 仅支持 1")
    job_id = await manager.enqueue("t2v", {
        "prompt": body.prompt, "duration": body.duration or 5.0,
        "size": body.size or "1280x720", "orientation": body.orientation or "16:9",
        "voiceover": body.voiceover, "provider": settings.T2V_PROVIDER,
        "response_format": body.response_format,
    }, _openai_t2v_job)
    return _job_openai(job_id, model=body.model)


def _openai_t2v_job(payload: dict, report) -> dict:
    report(0.02, "生成中…")
    result = t2v_engine.generate(
        payload["prompt"], duration=float(payload.get("duration", 5)),
        size=payload.get("size", "1280x720"), orientation=payload.get("orientation", "16:9"),
        voiceover=payload.get("voiceover"), provider=payload.get("provider", "local"), report=report)
    return {"kind": "video", "result": result}


# ------------------------------------------------------------------ edits
@router.post("/videos/edits", status_code=202)
async def video_edits(body: OpenAIVideoEditRequest, _: str = Depends(require_api_key)) -> dict:
    src = _resolve_video_source(body.video)
    if not src:
        raise _err("缺少 video（url / base64 / 已上传文件 id）")
    ops: List[Dict[str, Any]] = list(body.ops or [])
    if body.prompt:
        ops = _parse_prompt_ops(body.prompt) + ops
    if not ops:
        raise _err("未识别到任何编辑意图，请提供 prompt 或 ops")
    job_id = await manager.enqueue("video_edit", {
        "src": src, "ops": ops, "response_format": body.response_format,
    }, _openai_edit_job)
    return _job_openai(job_id, model=body.model)


def _resolve_video_source(video: Optional[str]) -> Optional[str]:
    if not video:
        return None
    video = video.strip()
    # uploaded file id (m_... or file_...)
    m = get_media(video)
    if m and Path(m["path"]).exists():
        return m["path"]
    # base64 data uri
    if video.startswith("data:"):
        try:
            head, _, b64 = video.partition(",")
            mime = head.split(";")[0].split(":")[1] if ":" in head else "video/mp4"
            ext = ".mp4" if "mp4" in mime else ".png"
            data = base64.b64decode(b64)
            p = settings.UPLOAD_DIR / f"api_{uuid.uuid4().hex[:10]}{ext}"
            p.write_bytes(data)
            return str(p)
        except Exception as exc:
            raise _err(f"base64 解码失败: {exc}") from exc
    # http(s) url
    if video.startswith("http://") or video.startswith("https://"):
        import urllib.request
        p = settings.UPLOAD_DIR / f"api_{uuid.uuid4().hex[:10]}.mp4"
        try:
            urllib.request.urlretrieve(video, p)
            return str(p)
        except Exception as exc:
            raise _err(f"下载视频失败: {exc}") from exc
    # local path fallback
    if Path(video).exists():
        return video
    return None


def _openai_edit_job(payload: dict, report) -> dict:
    report(0.05, "解析编辑意图…")
    src = payload["src"]
    ops = payload["ops"]
    # normalize op keys
    normalized = []
    for op in ops:
        if "op" not in op and "type" in op:
            op = {**op, "op": op["type"]}
        normalized.append(op)
    ops = normalized
    # handle remove-bg specially: produce alpha/composited output
    if any(o.get("op") in ("remove_bg", "remove-background", "background") for o in ops):
        report(0.3, "AI 背景消除…")
        is_video = _is_video(src)
        out = out_path(f"api_remove_{int(time.time())}", "webm" if is_video else "png")
        if is_video:
            remove_bg.remove_background_video(src, str(out), bg_color=None, report=report)
        else:
            remove_bg.remove_bg_image(src, str(out), bg_color=None, report=report)
        result = {"url": f"/exports/{out.name}", "file": str(out),
                  "format": "webm(alpha)" if is_video else "png(alpha)"}
        return {"kind": "video" if is_video else "image", "result": result}
    # subtitles special: transcribe + burn
    if any(o.get("op") in ("subtitles", "subtitle", "burn_subtitles") for o in ops):
        report(0.2, "语音转写…")
        segments = sub_engine.transcribe(src, lang="auto", report=report)
        srt = out_path(f"api_sub_{int(time.time())}", "srt", subdir="jobs")
        sub_engine.make_srt(segments, srt)
        out = out_path(f"api_subbed_{int(time.time())}", "mp4")
        sub_engine.burn_subtitles(src, str(srt), out, report=report)
        result = {"url": f"/exports/{out.name}", "file": str(out), "segments": segments[:5],
                  "segment_count": len(segments)}
        return {"kind": "video", "result": result}
    # generic ffmpeg ops pipeline
    report(0.15, "ffmpeg 处理中…")
    out = out_path(f"api_edit_{int(time.time())}", "mp4")
    apply_ops(src, ops, out, progress_cb=lambda p: report(0.15 + 0.8 * p, "处理中…"))
    result = {"url": f"/exports/{out.name}", "file": str(out)}
    return {"kind": "video", "result": result}


def _is_video(path: str) -> bool:
    try:
        info = probe_media(path)
        return info["width"] > 0 and info["duration"] > 0
    except Exception:
        return Path(path).suffix.lower() in VIDEO_EXT


# ------------------------------------------------------------------ job status
@router.get("/videos/{job_id}")
def video_status(job_id: str, _: str = Depends(require_api_key)) -> dict:
    job = get_job(job_id)
    if not job:
        raise _err(f"任务不存在: {job_id}", "not_found", 404)
    return _job_openai(job_id, job=job)


def _job_openai(job_id: str, model: str = "filmora-video", job: Optional[dict] = None) -> dict:
    job = job or get_job(job_id) or {}
    status = job.get("status", "queued")
    mapping = {"queued": "queued", "running": "in_progress", "completed": "completed", "failed": "failed"}
    result = None
    if job.get("result"):
        try:
            result = json.loads(job["result"]) if isinstance(job["result"], str) else job["result"]
        except Exception:
            result = job["result"]
    out: Dict[str, Any] = {
        "id": job_id,
        "object": "video.job",
        "model": model,
        "status": mapping.get(status, status),
        "created_at": int(job.get("created_at") or 0),
    }
    if status == "failed":
        try:
            err = json.loads(job["error"]) if isinstance(job["error"], str) else job["error"]
        except Exception:
            err = {"message": str(job.get("error", "任务失败"))}
        out["error"] = err
    if status == "completed" and result:
        r = result.get("result", result)
        url = r.get("url") or r.get("video_url")
        if url:
            abs_url = url if url.startswith("http") else f"{settings.public_base_url}{url}"
            item: Dict[str, Any] = {"url": abs_url, "type": "video/mp4"}
            _rf = (job.get("response_format") or "")
            if not _rf and job.get("payload"):
                try:
                    _rf = json.loads(job["payload"]).get("response_format", "")
                except Exception:
                    pass
            if _rf == "b64_json" and isinstance(r, dict) and "file" in r and Path(r["file"]).exists():
                try:
                    item["b64_json"] = base64.b64encode(Path(r["file"]).read_bytes()).decode()
                except Exception:
                    pass
            out["output"] = {"data": [item]}
            out["usage"] = {"prompt_tokens": 0, "total_tokens": 0}
    if status in ("queued", "running"):
        out["progress"] = job.get("progress", 0)
    return out


# ------------------------------------------------------------------ files
@router.post("/files")
async def upload_file(file: UploadFile = File(...), _: str = Depends(require_api_key)) -> dict:
    name = safe_name(file.filename or "media")
    ext = Path(name).suffix.lower()
    if ext not in VIDEO_EXT | IMAGE_EXT:
        raise _err(f"不支持的格式: {ext or '未知'}")
    media_id = "m_" + uuid.uuid4().hex[:12]
    dest = settings.UPLOAD_DIR / f"{media_id}_{name}"
    with open(dest, "wb") as out:
        while chunk := file.file.read(1024 * 1024):
            out.write(chunk)
    try:
        rec = make_media_record(str(dest), name, media_id,
                                kind="video" if ext in VIDEO_EXT else "image",
                                mime=file.content_type or "")
    except FFmpegError as exc:
        dest.unlink(missing_ok=True)
        raise _err(f"无法解析媒体: {exc}") from exc
    insert_media(rec)
    return {"id": media_id, "object": "file", "bytes": rec["size"], "filename": name, "purpose": "video-edit"}


@router.get("/files/{file_id}")
def file_info(file_id: str, _: str = Depends(require_api_key)) -> dict:
    m = get_media(file_id)
    if not m:
        raise _err("文件不存在", "not_found", 404)
    return {"id": file_id, "object": "file", "bytes": m["size"], "filename": m["name"], "purpose": "video-edit"}


@router.get("/files/{file_id}/content")
def file_content(file_id: str, _: str = Depends(require_api_key)) -> FileResponse:
    m = get_media(file_id)
    if not m or not Path(m["path"]).exists():
        raise _err("文件不存在", "not_found", 404)
    return FileResponse(m["path"], filename=m["name"])


# ------------------------------------------------------------------ prompt intent parser
def _parse_prompt_ops(prompt: str) -> List[Dict[str, Any]]:
    """Map natural-language edit instructions to structured ops."""
    ops: List[Dict[str, Any]] = []
    p = prompt.lower()

    def has(*keys: str) -> bool:
        return any(k in p for k in keys)

    if has("黑白", "black and white", "grayscale", "灰度", "b&w", "bw "):
        ops.append({"op": "filter", "filter": "bw"})
    if has("复古", "sepia", "棕"):
        ops.append({"op": "filter", "filter": "sepia"})
    if has("老电影", "vintage", "胶片"):
        ops.append({"op": "filter", "filter": "vintage"})
    if has("暖", "warm") and not has("冷暖"):
        ops.append({"op": "filter", "filter": "warm"})
    if has("冷", "cool") and not has("冷暖"):
        ops.append({"op": "filter", "filter": "cool"})
    if has("鲜艳", "vivid", "饱和"):
        ops.append({"op": "filter", "filter": "vivid"})
    if has("梦幻", "dream"):
        ops.append({"op": "filter", "filter": "dream"})
    if has("模糊", "blur"):
        ops.append({"op": "filter", "filter": "blur_soft"})
    if has("锐化", "sharpen", "清晰"):
        ops.append({"op": "filter", "filter": "sharpen"})
    if has("故障", "glitch"):
        ops.append({"op": "filter", "filter": "glitch"})
    if has("暗角", "vignette"):
        ops.append({"op": "filter", "filter": "vignette"})
    if has("反色", "invert", "负片"):
        ops.append({"op": "filter", "filter": "invert"})

    if has("去除背景", "去背景", "抠图", "抠像", "remove background", "remove the background", "background removal"):
        ops.append({"op": "remove_bg"})
    if has("字幕", "subtitles", "subtitle", "caption"):
        ops.append({"op": "subtitles"})

    m = re.search(r"(\d+(?:\.\d+)?)\s*[x×]\s*(加速|快进)|speed\s*up\s*(\d+(?:\.\d+)?)", p)
    if m:
        ops.append({"op": "speed", "factor": float(m.group(1) or m.group(3))})
    if has("倒放", "reverse", "倒着"):
        ops.append({"op": "reverse"})

    m = re.search(r"慢放|slow\s*down|slow\s*motion", p)
    if m:
        ops.append({"op": "speed", "factor": 0.5})

    m = re.search(r"(\d{3,4})\s*[xX×]\s*(\d{3,4})", p)
    if m and not any(o.get("op") == "resize" for o in ops):
        ops.append({"op": "resize", "width": int(m.group(1)), "height": int(m.group(2))})
    if has("竖屏", "9:16", "vertical"):
        ops.append({"op": "resize", "width": 1080, "height": 1920})
    if has("方形", "1:1", "square"):
        ops.append({"op": "resize", "width": 1080, "height": 1080})

    m = re.search(r"rotate\s*(\d+)", p)
    if m:
        ops.append({"op": "rotate", "angle": int(m.group(1))})
    m = re.search(r"裁剪\s*(\d+(?:\.\d+)?)\s*到\s*(\d+(?:\.\d+)?)|trim\s*(\d+(?:\.\d+)?)\s*to\s*(\d+(?:\.\d+)?)", p)
    if m:
        s = float(m.group(1) or m.group(3)); e = float(m.group(2) or m.group(4))
        ops.append({"op": "trim", "start": s, "end": e})
    return ops
