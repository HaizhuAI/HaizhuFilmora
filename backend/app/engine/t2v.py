"""Text-to-video generation.

provider=local : deterministic local generator — animated gradient/scene frames +
                 dynamic title text + optional TTS voiceover -> real MP4.
provider=openai: forward to an external OpenAI-compatible video API
                 (T2V_API_BASE + T2V_API_KEY), returns its URL or file.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..config import settings
from .ffmpeg import run_ffmpeg

FPS = 24


def generate(prompt: str, duration: float = 5.0, size: str = "1280x720",
             orientation: str = "16:9", voiceover: Optional[str] = None,
             lang: str = "auto", provider: str = "local",
             report=None) -> Dict[str, Any]:
    provider = provider or settings.T2V_PROVIDER
    if provider == "openai":
        return _generate_openai(prompt, duration, size, orientation, voiceover, report)
    return _generate_local(prompt, duration, size, orientation, voiceover, report)


# ----------------------------------------------------------------------
# local generator
# ----------------------------------------------------------------------
def _palette_for(prompt: str) -> List[tuple]:
    h = hashlib.md5(prompt.encode()).hexdigest()
    base = int(h[:6], 16)
    def hue_color(hue: float, sat: float = 0.62, val: float = 0.62) -> tuple:
        import colorsys
        r, g, b = colorsys.hsv_to_rgb((hue % 1.0), sat, val)
        return (int(r * 255), int(g * 255), int(b * 255))
    c1 = hue_color((base & 0xFF) / 255.0)
    c2 = hue_color(((base >> 8) & 0xFF) / 255.0, 0.5, 0.35)
    c3 = hue_color(((base >> 16) & 0xFF) / 255.0, 0.75, 0.75)
    return [c1, c2, c3]


def _scenes_for(prompt: str, duration: float) -> int:
    return max(1, min(4, int(duration // 3) + 1))


def _render_scene(img: Image.Image, prompt: str, t: float, scene_idx: int, total_scenes: int,
                  palette: List[tuple], size: tuple) -> Image.Image:
    """Draw one animated frame: gradient + drifting shapes + title."""
    w, h = size
    draw = ImageDraw.Draw(img, "RGBA")
    c0, c1, c2 = palette
    # gradient background with slow drift
    phase = t * 0.15
    for y in range(0, h, 4):
        tt = y / h
        mix = (tt + phase * 0.08) % 1.0
        if mix < 0.5:
            col = tuple(int(a + (b - a) * mix * 2) for a, b in zip(c0, c1))
        else:
            col = tuple(int(a + (b - a) * (mix - 0.5) * 2) for a, b in zip(c1, c2))
        draw.line([(0, y), (w, y)], fill=col)
    # soft light orb moving
    orb_x = int(w * (0.5 + 0.45 * math.sin(t * 0.5 + scene_idx)))
    orb_y = int(h * (0.35 + 0.25 * math.cos(t * 0.6)))
    for r, a in ((180, 26), (110, 40), (55, 60)):
        draw.ellipse([orb_x - r, orb_y - r, orb_x + r, orb_y + r], fill=c2 + (a,))
    # drifting particles
    rnd = random.Random(scene_idx * 999 + int(t * 8))
    for _ in range(12):
        px = int((rnd.random() * w + t * 14 * (rnd.random() - 0.5) + scene_idx * 40) % w)
        py = int((rnd.random() * h + math.sin(t + scene_idx) * 8) % h)
        draw.ellipse([px - 2, py - 2, px + 2, py + 2], fill=(255, 255, 255, 90))
    # title text with fade-in
    fade = min(1.0, max(0.0, (t - 0.3) / 0.8))
    title = _wrap_text(prompt, 26)
    try:
        font = ImageFont.truetype(_find_font(), 64)
    except Exception:
        font = ImageFont.load_default()
    alpha = int(230 * fade)
    shadow = (0, 0, 0, int(120 * fade))
    y0 = int(h * 0.32)
    for i, line in enumerate(title[:3]):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) / 2
        yy = y0 + i * 84
        draw.text((x + 3, yy + 3), line, font=font, fill=shadow)
        draw.text((x, yy), line, font=font, fill=(255, 255, 255, alpha))
    # footer chip
    draw.rounded_rectangle([w - 340, h - 92, w - 40, h - 52], radius=10, fill=(0, 0, 0, 110))
    try:
        small = ImageFont.truetype(_find_font(), 22)
    except Exception:
        small = font
    draw.text((w - 320, h - 84), f"Filmora WebUI · scene {scene_idx+1}/{total_scenes}", font=small, fill=(255, 255, 255, 160))
    return img


def _wrap_text(text: str, max_len: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > max_len and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def _find_font() -> str:
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "C:/Windows/Fonts/msyh.ttc"):
        if os.path.exists(p):
            return p
    return ""


def _generate_local(prompt: str, duration: float, size: str, orientation: str,
                    voiceover: Optional[str], report=None) -> Dict[str, Any]:
    if report:
        report(0.05, "本地文生视频生成中…")
    duration = max(1.5, min(duration, 30.0))
    w, h = _parse_size(size, orientation)
    palette = _palette_for(prompt)
    scenes = _scenes_for(prompt, duration)
    seg_dur = duration / scenes
    out = settings.EXPORT_DIR / f"t2v_{int(time.time())}.mp4"

    tmp = tempfile.mkdtemp(prefix="t2v_")
    frame_paths: List[str] = []
    total_frames = int(duration * FPS)
    for i in range(total_frames):
        t = i / FPS
        scene_idx = min(scenes - 1, int(t / seg_dur))
        img = Image.new("RGB", (w, h))
        img = _render_scene(img, prompt, t % seg_dur, scene_idx, scenes, palette, (w, h))
        fp = os.path.join(tmp, f"f{i:06d}.png")
        img.save(fp)
        frame_paths.append(fp)
        if report and i % max(1, total_frames // 10) == 0:
            report(0.1 + 0.55 * i / total_frames, f"渲染帧 {i}/{total_frames}")
    if report:
        report(0.68, "编码视频…")

    audio_args: List[str] = []
    if voiceover and voiceover.strip():
        audio_path = _synthesize_tts(voiceover, tmp)
        if audio_path:
            audio_args = ["-i", audio_path, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    args = ["-framerate", str(FPS), "-i", os.path.join(tmp, "f%06d.png")]
    if not audio_args:
        args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    else:
        args += audio_args
    args += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(out)]
    run_ffmpeg(args, progress_cb=lambda p: report and report(0.7 + 0.25 * p, "编码…"))

    for fp in frame_paths:
        try:
            os.remove(fp)
        except OSError:
            pass
    return {
        "provider": "local",
        "prompt": prompt,
        "duration": round(duration, 2),
        "size": f"{w}x{h}",
        "video_url": f"/exports/{out.name}",
        "file": str(out),
    }


def _synthesize_tts(text: str, tmpdir: str) -> Optional[str]:
    """TTS via edge-tts if installed; else None (silent)."""
    try:
        import edge_tts  # type: ignore
        import asyncio
        out = os.path.join(tmpdir, "voice.mp3")
        async def _run():
            comm = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
            await comm.save(out)
        asyncio.run(_run())
        return out if os.path.exists(out) and os.path.getsize(out) > 0 else None
    except Exception:
        return None


def _parse_size(size: str, orientation: str) -> tuple:
    if "x" in size:
        try:
            w, h = (int(x) for x in size.lower().split("x")[:2])
            return w, h
        except Exception:
            pass
    return {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080)}.get(
        orientation, (1280, 720))


# ----------------------------------------------------------------------
# external OpenAI-compatible provider
# ----------------------------------------------------------------------
def _generate_openai(prompt: str, duration: float, size: str, orientation: str,
                     voiceover: Optional[str], report=None) -> Dict[str, Any]:
    base = settings.T2V_API_BASE.rstrip("/")
    if not base:
        raise RuntimeError("T2V_PROVIDER=openai 但未配置 T2V_API_BASE")
    if report:
        report(0.1, "调用外部文生视频 API…")
    body = {
        "model": settings.T2V_MODEL,
        "prompt": prompt,
        "duration": duration,
        "size": _parse_size(size, orientation) and size,
        "response_format": "url",
    }
    req = urllib.request.Request(
        f"{base}/v1/videos/generations",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {settings.T2V_API_KEY}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        raise RuntimeError(f"外部文生视频 API 失败: {exc}") from exc
    data.setdefault("provider", "openai")
    return data
