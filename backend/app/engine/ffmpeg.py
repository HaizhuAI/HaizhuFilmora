"""ffmpeg/ffprobe wrapper for core video editing operations."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings


class FFmpegError(RuntimeError):
    pass


def _run(cmd: List[str], timeout: Optional[int] = None) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise FFmpegError(f"未找到 {cmd[0]}，请先安装 ffmpeg") from exc
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"命令超时: {' '.join(cmd[:6])}...") from exc
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr[-1500:] or f"ffmpeg 返回码 {proc.returncode}")
    return proc.stdout


def ffprobe(path: str) -> Dict[str, Any]:
    out = _run([settings.FFPROBE_BIN, "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path])
    return json.loads(out)


def probe_media(path: str) -> Dict[str, Any]:
    info = ffprobe(path)
    vstream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    astream = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = info.get("format", {})
    duration = float(fmt.get("duration") or (vstream or {}).get("duration") or 0)
    return {
        "duration": duration,
        "width": int((vstream or {}).get("width") or 0),
        "height": int((vstream or {}).get("height") or 0),
        "fps": _fps_of(vstream),
        "has_audio": bool(astream),
        "vcodec": (vstream or {}).get("codec_name", ""),
        "acodec": (astream or {}).get("codec_name", ""),
        "size_bytes": int(fmt.get("size") or os.path.getsize(path)),
    }


def _fps_of(vstream: Optional[Dict[str, Any]]) -> float:
    if not vstream:
        return 0.0
    r = vstream.get("avg_frame_rate") or vstream.get("r_frame_rate") or "0/1"
    try:
        num, den = r.split("/")
        return round(float(num) / float(den), 3) if float(den) else 0.0
    except Exception:
        return 0.0


def make_media_record(path: str, name: str, media_id: str, kind: str = "video", mime: str = "") -> Dict[str, Any]:
    p = probe_media(path)
    return {
        "id": media_id,
        "name": name,
        "path": str(path),
        "mime": mime or "video/mp4",
        "size": p["size_bytes"],
        "duration": p["duration"],
        "width": p["width"],
        "height": p["height"],
        "kind": kind,
        "created_at": __import__("time").time(),
    }


def safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


def out_path(prefix: str, ext: str, subdir: str = "exports") -> Path:
    d = settings.DATA_DIR / subdir
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{prefix}_{os.urandom(4).hex()}.{ext}"


# ------------------------------------------------------------------
# video ops
# ------------------------------------------------------------------
def run_ffmpeg(args: List[str], progress_cb=None, timeout: Optional[int] = None) -> None:
    _run([settings.FFMPEG_BIN, "-y"] + args, timeout=timeout)
    if progress_cb:
        progress_cb(0.95)


def _base_out_args(out: Path, export: Optional[Dict[str, Any]] = None) -> List[str]:
    export = export or {}
    args: List[str] = []
    vcodec = export.get("vcodec", "libx264")
    args += ["-c:v", vcodec]
    if vcodec == "libx264":
        args += ["-preset", export.get("preset", "medium"), "-crf", str(export.get("crf", settings.EXPORT_CRF))]
    if export.get("pixel_format"):
        args += ["-pix_fmt", export["pixel_format"]]
    if export.get("bitrate"):
        args += ["-b:v", str(export["bitrate"])]
    if export.get("acodec", "aac") == "copy" or export.get("keep_audio") is False:
        args += ["-an"]
    else:
        args += ["-c:a", export.get("acodec", "aac"), "-b:a", "192k"]
    if export.get("fps"):
        args += ["-r", str(export["fps"])]
    args += ["-movflags", "+faststart"]
    args += ["-progress", "pipe:1"]
    args += [str(out)]
    return args


def _scale_filter(width: Optional[int] = None, height: Optional[int] = None, orientation: Optional[str] = None) -> str:
    if orientation:
        if orientation in ("9:16", "vertical"):
            return "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black"
        if orientation == "1:1":
            return "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:color=black"
        if orientation in ("16:9", "horizontal"):
            return "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black"
    if width and height:
        return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black"
    return ""


def apply_ops(media_path: str, ops: List[Dict[str, Any]], out: Path, export: Optional[Dict[str, Any]] = None, progress_cb=None) -> Path:
    """Apply a list of edit operations to a video and export."""
    export = export or {}
    input_args: List[str] = ["-i", media_path]
    vf_parts: List[str] = []
    af_parts: List[str] = []
    trim: Optional[Dict[str, Any]] = None
    speed = float(export.get("speed") or 1.0)
    seek = 0.0

    for op in ops:
        kind = op.get("op", op.get("type", ""))
        if kind in ("trim", "cut"):
            trim = op
            seek = float(op.get("start") or 0.0)
        elif kind == "speed":
            speed = float(op.get("factor") or op.get("speed") or 1.0)
        elif kind == "reverse":
            vf_parts.append("reverse")
        elif kind in ("rotate", "rot"):
            angle = int(op.get("angle", 90))
            if angle == 90:
                vf_parts.append("transpose=1")
            elif angle == 270:
                vf_parts.append("transpose=2")
            elif angle == 180:
                vf_parts.append("hflip,vflip")
        elif kind == "flip":
            if op.get("direction") == "horizontal":
                vf_parts.append("hflip")
            elif op.get("direction") == "vertical":
                vf_parts.append("vflip")
        elif kind == "crop":
            w = op.get("width"); h = op.get("height")
            x = op.get("x", "iw/2-{}/2".format(w) if w else "(iw-ow)/2")
            y = op.get("y", "ih/2-{}/2".format(h) if h else "(ih-oh)/2")
            vf_parts.append(f"crop={w}:{h}:{x}:{y}")
        elif kind == "resize":
            vf_parts.append(f"scale={op.get('width', -2)}:{op.get('height', -2)}")
        elif kind == "filter":
            fname = op.get("filter") or op.get("name")
            strength = float(op.get("strength") or op.get("intensity") or 1.0)
            vf_parts.append(filter_chain(fname, strength))
        elif kind == "text":
            vf_parts.append(drawtext_chain(op))
        elif kind == "subtitle":
            vf_parts.append(subtitle_chain(op))
        elif kind == "volume":
            af_parts.append(f"volume={float(op.get('volume', 1.0))}")
        elif kind == "mute":
            af_parts.append("volume=0")
        elif kind == "audio_extract":
            af_parts.append("anull")  # handled specially below
        elif kind == "blur":
            vf_parts.append(f"boxblur={op.get('sigma', 10)}:{op.get('sigma', 10)}")
        elif kind == "bgm":
            # background music mix
            bgm = op.get("path")
            if bgm and Path(bgm).exists():
                input_args += ["-i", str(bgm)]
                vf_parts.append("null")
                # handled in filter_complex style
                return _apply_ops_complex(media_path, ops, out, export, progress_cb)

    # speed via setpts (audio atempo)
    if speed != 1.0:
        vf_parts.append(f"setpts={1.0/speed:.6f}*PTS")
        if af_parts or True:
            tempo = speed
            chain = ""
            while tempo > 2.0:
                chain += "atempo=2.0,"
                tempo /= 2.0
            while tempo < 0.5:
                chain += "atempo=0.5,"
                tempo /= 0.5
            chain += f"atempo={tempo:.6f}"
            af_parts.append(chain)

    scale = _scale_filter(export.get("width"), export.get("height"), export.get("orientation"))
    if scale:
        vf_parts.append(scale)

    args = input_args[:]
    if seek > 0:
        # fast seek + accurate trim
        args = ["-ss", f"{seek:.3f}"] + args
    if trim:
        dur = trim.get("duration")
        if dur is None and trim.get("end") is not None:
            dur = float(trim["end"]) - seek
        if dur and dur > 0:
            args += ["-t", f"{dur:.3f}"]
    if vf_parts:
        args += ["-vf", ",".join(vf_parts)]
    if af_parts:
        args += ["-af", ",".join(af_parts)]
    args += _base_out_args(out, export)
    run_ffmpeg(args, progress_cb=progress_cb)
    return out


def _apply_ops_complex(media_path: str, ops: List[Dict[str, Any]], out: Path, export: Optional[Dict[str, Any]], progress_cb=None) -> Path:
    """Fallback for ops that need filter_complex (e.g. bgm mixing)."""
    # simple path: use amix for bgm
    bgm = next((op["path"] for op in ops if op.get("op") == "bgm"), None)
    args = ["-i", media_path, "-i", str(bgm), "-filter_complex",
            "[0:a]volume=0.85[va];[1:a]volume=0.4[ma];[va][ma]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map", "0:v", "-map", "[aout]"]
    args += _base_out_args(out, export)
    run_ffmpeg(args, progress_cb=progress_cb)
    return out


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------
def drawtext_chain(op: Dict[str, Any]) -> str:
    text = (op.get("text") or "").replace(":", "\\:").replace("'", "")
    x = op.get("x", "w/2-tw/2")
    y = op.get("y", "h*0.85")
    fontsize = int(op.get("font_size", 48))
    color = op.get("color", "white")
    font = op.get("font", "Sans")
    border = int(op.get("border", 0))
    box = "1" if op.get("box") else "0"
    shadow = int(op.get("shadow", 0))
    # time display placeholder for dynamic text
    if op.get("dynamic") == "timestamp":
        text = "%{pts\\:hms}"
    chain = (f"drawtext=text='{text}':x={x}:y={y}:fontsize={fontsize}:fontcolor={color}"
             f":fontfile={font}:box={box}:boxcolor=black@0.5:boxborderw={border}"
             f":shadowx={shadow}:shadowy={shadow}")
    if op.get("dynamic") == "timestamp":
        chain = chain.replace(f"text='{text}'", "text='%{pts\\:hms}'")
    return chain


def subtitle_chain(op: Dict[str, Any]) -> str:
    path = op.get("path")
    if not path or not Path(path).exists():
        return "null"
    return f"subtitles={path}:force_style='FontSize={op.get('font_size', 18)},PrimaryColour={op.get('color', '&H00FFFFFF')}'"


def filter_chain(name: str, strength: float = 1.0) -> str:
    """Map app filter ids to ffmpeg filter chains."""
    from .filters import FILTERS
    spec = FILTERS.get(name or "", FILTERS["none"])
    chain = spec.get("ffmpeg", "null")
    # simple strength interpolation for common params
    if "{s}" in chain:
        chain = chain.format(s=strength)
    return chain


def concat_videos(paths: List[str], out: Path, export: Optional[Dict[str, Any]] = None, progress_cb=None) -> Path:
    """Concatenate videos (same codec family recommended; re-encode fallback)."""
    if len(paths) == 1:
        shutil.copyfile(paths[0], out)
        return out
    # demuxer concat
    list_file = out.with_suffix(".txt")
    with open(list_file, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    export = export or {}
    args = ["-f", "concat", "-safe", "0", "-i", str(list_file)]
    args += _base_out_args(out, export)
    try:
        run_ffmpeg(args, progress_cb=progress_cb)
    except FFmpegError:
        # fallback: filter concat with re-encode
        args = []
        for p in paths:
            args += ["-i", p]
        inputs = "".join(f"[{i}:v][{i}:a]" for i in range(len(paths)))
        args += ["-filter_complex", f"{inputs}concat=n={len(paths)}:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]"]
        args += _base_out_args(out, export)
        run_ffmpeg(args, progress_cb=progress_cb)
    return out


def extract_audio(media_path: str, out: Path, progress_cb=None) -> Path:
    run_ffmpeg(["-i", media_path, "-vn", "-c:a", "mp3", "-b:a", "192k", str(out)], progress_cb=progress_cb)
    return out


def make_gif(media_path: str, out: Path, start: float = 0.0, duration: float = 3.0, fps: int = 12, width: int = 480, progress_cb=None) -> Path:
    args = ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", media_path,
            "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            "-loop", "0", str(out)]
    run_ffmpeg(args, progress_cb=progress_cb)
    return out


def make_thumbnail(media_path: str, out: Path, at: float = 1.0, progress_cb=None) -> Path:
    run_ffmpeg(["-ss", f"{at:.3f}", "-i", media_path, "-frames:v", "1", "-q:v", "2", str(out)], progress_cb=progress_cb)
    return out
