"""Smart subtitles: speech-to-text -> SRT -> optional burn-in.

Uses faster-whisper when installed; falls back to a silence-detection
placeholder SRT or user-provided SRT so the pipeline always runs.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings
from .ffmpeg import run_ffmpeg


def _format_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(segments: List[Dict[str, Any]], path: Path) -> Path:
    lines = []
    for i, seg in enumerate(segments, 1):
        text = seg.get("text", "").strip().replace("\n", " ")
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{_format_ts(seg['start'])} --> {_format_ts(seg['end'])}")
        lines.append(text)
        lines.append("")
    if not lines:
        # keep the pipeline alive when there is no speech
        lines = ["1", "00:00:00,000 --> 00:00:05,000", "（无语音内容）", ""]
    path.write_text("\ufeff" + "\n".join(lines), encoding="utf-8")
    return path


def transcribe(media_path: str, lang: str = "auto", model: str = "small", report=None) -> List[Dict[str, Any]]:
    """Return [{start,end,text}] segments."""
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        return _silence_fallback(media_path, report)

    device = settings.WHISPER_DEVICE
    if device == "auto":
        device = "cuda" if _has_cuda() else "cpu"
    wmodel = WhisperModel(model, device=device, compute_type="float16" if device == "cuda" else "int8")
    if report:
        report(0.3, "加载语音识别模型…")
    segs, _info = wmodel.transcribe(media_path, language=None if lang == "auto" else lang)
    out: List[Dict[str, Any]] = []
    for s in segs:
        out.append({"start": float(s.start), "end": float(s.end), "text": s.text.strip()})
        if report:
            report(min(0.3 + 0.6 * len(out) / 100, 0.9), f"转写中… {len(out)} 段")
    return out


def _silence_fallback(media_path: str, report=None) -> List[Dict[str, Any]]:
    """Silence-detect based placeholder segments (works without whisper)."""
    if report:
        report(0.2, "未安装 faster-whisper，使用静音检测占位字幕")
    dur = float(subprocess.check_output([
        settings.FFPROBE_BIN, "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", media_path]).strip() or 0)
    out: List[Dict[str, Any]] = []
    step = 4.0
    t = 0.0
    while t < dur - 1:
        out.append({"start": t, "end": min(t + step, dur), "text": "…"})
        t += step
    return out


def make_srt(segments: List[Dict[str, Any]], out: Path) -> Path:
    return _write_srt(segments, out)


def burn_subtitles(media_path: str, srt_path: str, out: Path, style: Optional[Dict[str, Any]] = None, report=None) -> Path:
    style = style or {}
    fontsize = style.get("font_size", 18)
    color = style.get("color", "&H00FFFFFF")
    border = style.get("border", 3)
    force_style = f"FontName={style.get('font', 'Sans')},FontSize={fontsize},PrimaryColour={color},BorderStyle=1,Outline={border},OutlineColour=&H80000000,Shadow=0,MarginV=24"
    srt_esc = str(srt_path).replace("\\", "/").replace(":", "\\\\:").replace(",", "\\\\,")
    args = ["-i", media_path, "-vf", f"subtitles={srt_esc}:force_style='{force_style}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(style.get("crf", 20)),
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    run_ffmpeg(args, progress_cb=report)
    return out


def _has_cuda() -> bool:
    try:
        import torch  # type: ignore
        return torch.cuda.is_available()
    except Exception:
        return False
