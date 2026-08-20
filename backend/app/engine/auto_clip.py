"""AI auto-clip: scene detection + highlight selection.

Uses PySceneDetect when installed; ffmpeg scene filter as fallback.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings
from .ffmpeg import run_ffmpeg, out_path


def detect_scenes(media_path: str, threshold: float = 0.35, report=None) -> List[Dict[str, Any]]:
    """Return list of {start,end} scene segments."""
    try:
        import scenedetect  # type: ignore
        return _detect_with_scenedetect(media_path, threshold, report)
    except Exception:
        return _detect_with_ffmpeg(media_path, threshold, report)


def _detect_with_scenedetect(media_path: str, threshold: float, report=None) -> List[Dict[str, Any]]:
    from scenedetect import detect, ContentDetector, split_video_ffmpeg  # noqa: F401
    from scenedetect.scene_manager import SceneManager
    from scenedetect.video_manager import VideoManager
    if report:
        report(0.2, "PySceneDetect 分析场景…")
    video = VideoManager([media_path])
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=threshold))
    video.set_downscale_factor(2)
    sm.detect_scenes(video, show_progress=False)
    scene_list = sm.get_scene_list()
    video.release()
    out = [{"start": float(s[0].get_seconds()), "end": float(s[1].get_seconds())} for s in scene_list]
    return out


def _detect_with_ffmpeg(media_path: str, threshold: float, report=None) -> List[Dict[str, Any]]:
    if report:
        report(0.2, "ffmpeg scene 检测…")
    # get scene change frame timestamps via select filter
    cmd = [settings.FFMPEG_BIN, "-i", media_path, "-vf", f"select='gt(scene,{threshold})',showinfo",
           "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    pts_list = []
    for line in proc.stderr.splitlines():
        if "showinfo" in line and "pts_time:" in line:
            try:
                pts = float(line.split("pts_time:")[1].split()[0])
                pts_list.append(pts)
            except Exception:
                pass
    dur = _duration(media_path)
    boundaries = [0.0] + pts_list + [dur]
    out = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        if e - s >= 0.5:
            out.append({"start": round(s, 2), "end": round(e, 2)})
    return out


def _duration(media_path: str) -> float:
    out = subprocess.check_output([
        settings.FFPROBE_BIN, "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", media_path]).decode().strip()
    try:
        return float(out)
    except Exception:
        return 0.0


def auto_clip(media_path: str, mode: str = "highlights", max_clips: int = 5, min_clip_seconds: float = 1.0,
              out_dir: Optional[Path] = None, report=None) -> Dict[str, Any]:
    """Auto-clip into segments; 'highlights' picks the most visually active segments."""
    scenes = detect_scenes(media_path, report=report)
    if not scenes:
        raise RuntimeError("未检测到场景变化")
    if mode == "highlights":
        # score by length, prefer segments near 3-8s
        scored = []
        for s in scenes:
            dur = s["end"] - s["start"]
            score = min(dur, 8.0) / 8.0 + (0.5 if 3 <= dur <= 10 else 0)
            scored.append((score, s))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [s for _, s in scored[:max_clips]]
        selected.sort(key=lambda x: x["start"])
    else:
        selected = [s for s in scenes if (s["end"] - s["start"]) >= min_clip_seconds][:max_clips]

    out_dir = out_dir or settings.EXPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, seg in enumerate(selected):
        out = out_dir / f"clip_{i+1:02d}_{seg['start']:.1f}_{seg['end']:.1f}.mp4"
        run_ffmpeg([
            "-ss", f"{seg['start']:.3f}", "-t", f"{seg['end']-seg['start']:.3f}",
            "-i", media_path, "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
        ], progress_cb=lambda p: report and report(0.3 + 0.6 * (i + 1) / len(selected), f"裁剪片段 {i+1}/{len(selected)}"))
        clips.append({"index": i + 1, "start": seg["start"], "end": seg["end"],
                      "duration": round(seg["end"] - seg["start"], 2), "path": str(out), "url": out.name})
    return {"mode": mode, "scenes": scenes, "clips": clips}
