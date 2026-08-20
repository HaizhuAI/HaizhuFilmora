"""AI removal: background removal + object (mask) removal.

Primary backend: rembg (u2net) when installed.
Fallbacks that always run:
  - background: OpenCV GrabCut seeded from borders + alpha mask -> transparent/composited bg
  - object: OpenCV inpainting on a user-supplied mask (or center-rect default)
Video mode: sample frames -> process -> reassemble with ffmpeg.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from ..config import settings
from .ffmpeg import run_ffmpeg


def _has_rembg() -> bool:
    try:
        import rembg  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def _rembg_session():
    from rembg import new_session  # type: ignore
    return new_session("u2net")


def remove_bg_image(input_path: str, out_path: str, bg_color: Optional[tuple] = None, report=None) -> str:
    """Remove background from image. Returns output path (RGBA or composited)."""
    img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"无法读取图片: {input_path}")

    if _has_rembg():
        import rembg
        if report:
            report(0.3, "rembg 处理中…")
        data = open(input_path, "rb").read()
        result = rembg.remove(data, session=_rembg_session())
        arr = np.frombuffer(result, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    else:
        if report:
            report(0.3, "未安装 rembg，使用 GrabCut 边界分割")
        img = _grabcut_bg(img)

    if bg_color is not None:
        rgba = img
        if rgba.shape[2] == 3:
            rgba = cv2.cvtColor(rgba, cv2.COLOR_BGR2BGRA)
        alpha = rgba[:, :, 3] / 255.0
        bg = np.full(rgba.shape, list(bg_color) + [255], dtype=np.uint8)
        comp = (rgba[:, :, :3].astype(np.float32) * alpha[..., None] +
                bg[:, :, :3].astype(np.float32) * (1 - alpha[..., None])).astype(np.uint8)
        cv2.imwrite(out_path, comp)
    else:
        cv2.imwrite(out_path, img)
    return out_path


def _grabcut_bg(img: np.ndarray) -> np.ndarray:
    """Naive GrabCut segmentation: treat image borders as background."""
    h, w = img.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    # border band as definite background
    band = max(2, min(h, w) // 25)
    mask[:band, :] = getattr(cv2, "GC_BG_FULL", cv2.GC_BGD)
    mask[-band:, :] = getattr(cv2, "GC_BG_FULL", cv2.GC_BGD)
    mask[:, :band] = getattr(cv2, "GC_BG_FULL", cv2.GC_BGD)
    mask[:, -band:] = getattr(cv2, "GC_BG_FULL", cv2.GC_BGD)
    mask[band:-band, band:-band] = cv2.GC_PR_FGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        mask, _, _ = cv2.grabCut(img, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    except Exception:
        mask = np.full((h, w), cv2.GC_PR_FGD, np.uint8)
    alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    # soften edges
    alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
    bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    return bgra


def remove_object_image(input_path: str, out_path: str, mask: Optional[Dict[str, Any]] = None, report=None) -> str:
    """Remove an object via inpainting. mask: {x,y,w,h} or user mask image path."""
    img = cv2.imread(input_path)
    if img is None:
        raise RuntimeError(f"无法读取图片: {input_path}")
    h, w = img.shape[:2]
    m = np.zeros((h, w), np.uint8)
    if mask and mask.get("path") and Path(mask["path"]).exists():
        m = cv2.imread(mask["path"], cv2.IMREAD_GRAYSCALE)
    else:
        x = int(mask.get("x", w * 0.3)) if mask else int(w * 0.3)
        y = int(mask.get("y", h * 0.3)) if mask else int(h * 0.3)
        bw = int(mask.get("width", w * 0.4)) if mask else int(w * 0.4)
        bh = int(mask.get("height", h * 0.4)) if mask else int(h * 0.4)
        m[y:y+bh, x:x+bw] = 255
    m = cv2.dilate(m, np.ones((7, 7), np.uint8), iterations=1)
    if report:
        report(0.5, "OpenCV inpainting…")
    inpainted = cv2.inpaint(img, m, 5, cv2.INPAINT_TELEA)
    cv2.imwrite(out_path, inpainted)
    return out_path


def remove_background_video(input_path: str, out_path: str, bg_color: Optional[str] = None, report=None) -> str:
    """Extract keyframes, remove bg, rebuild video with ffmpeg."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        frames_dir = td / "frames"
        out_dir = td / "out"
        frames_dir.mkdir(); out_dir.mkdir()
        probe = subprocess.check_output([
            settings.FFPROBE_BIN, "-v", "quiet", "-select_streams", "v:0",
            "-show_entries", "stream=nb_frames,r_frame_rate,width,height",
            "-of", "json", input_path]).decode()
        import json
        info = json.loads(probe)
        st = (info.get("streams") or [{}])[0]
        fps = st.get("r_frame_rate", "25/1")
        try:
            num, den = fps.split("/")
            fps_f = float(num) / float(den)
        except Exception:
            fps_f = 25.0
        if report:
            report(0.2, "抽取视频帧…")
        subprocess.run([settings.FFMPEG_BIN, "-y", "-i", input_path, "-vf", "fps=10", f"{frames_dir}/f%05d.png"],
                       capture_output=True, check=True)
        frames = sorted(frames_dir.glob("*.png"))
        if not frames:
            raise RuntimeError("无帧可处理")
        bg = _parse_color(bg_color)
        total = len(frames)
        for i, fp in enumerate(frames):
            remove_bg_image(str(fp), str(out_dir / fp.name), bg_color=bg, report=None)
            if report and i % max(1, total // 10) == 0:
                report(0.2 + 0.6 * i / total, f"AI 消除 {i}/{total}")
        if report:
            report(0.85, "重组视频…")
        # re-encode transparent PNG sequence to video with alpha (qtrle) or composite on black
        if bg is None:
            vcodec = "libvpx-vp9"
            args = ["-framerate", str(fps_f), "-i", f"{out_dir}/f%05d.png",
                    "-c:v", vcodec, "-pix_fmt", "yuva420p", "-b:v", "2M", str(out_path)]
        else:
            args = ["-framerate", str(fps_f), "-i", f"{out_dir}/f%05d.png",
                    "-vf", f"format=rgba,color=c={bg}@1.0:s={st.get('width','1280')}x{st.get('height','720')}[bg];[bg][0]overlay=shortest=1",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", str(out_path)]
        run_ffmpeg(args, progress_cb=report)
    return out_path


def _parse_color(color: Optional[str]) -> Optional[tuple]:
    if not color:
        return None
    color = color.lstrip("#")
    if len(color) == 6:
        return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    if len(color) == 3:
        return tuple(int(c * 2, 16) for c in color)
    return None
