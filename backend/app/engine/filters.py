"""Filter & effect presets ported from the app's assets/filters shader set to ffmpeg chains.

The APK ships GLSL fragment shaders (assets/filters/*/fragment.fs) for real-time
preview. On the server we realize the same look with equivalent ffmpeg filter
graphs so results can be burned into exports.
"""
from __future__ import annotations

FILTERS: dict[str, dict] = {
    "none":       {"name": "原始", "ffmpeg": "null"},
    "bw":         {"name": "黑白", "ffmpeg": "hue=s=0,eq=contrast=1.05:brightness=0.02"},
    "sepia":      {"name": "复古棕", "ffmpeg": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131:0"},
    "vintage":    {"name": "老电影", "ffmpeg": "curves=vintage,noise=alls=6:allf=t+u,eq=saturation=0.75"},
    "warm":       {"name": "暖阳", "ffmpeg": "colortemperature=temperature=6500,eq=saturation=1.1"},
    "cool":       {"name": "冷调", "ffmpeg": "colortemperature=temperature=4500,eq=saturation=0.9"},
    "vivid":      {"name": "鲜艳", "ffmpeg": "eq=saturation=1.6:contrast=1.12:brightness=0.02"},
    "fade":       {"name": "胶片淡雅", "ffmpeg": "eq=saturation=0.8:contrast=0.95:brightness=0.03,curves=all='0/0.08 0.5/0.5 1/0.92'"},
    "night":      {"name": "夜色", "ffmpeg": "eq=brightness=-0.12:saturation=0.7,colorbalance=bs=-0.15:ms=0.1"},
    "dream":      {"name": "梦幻", "ffmpeg": "gblur=sigma=1.5,eq=saturation=1.3:brightness=0.05,curves=all='0/0.1 1/0.9'"},
    "noir":       {"name": "暗黑", "ffmpeg": "hue=s=0,eq=contrast=1.35:brightness=-0.05"},
    "sunset":     {"name": "落日", "ffmpeg": "colorbalance=rs=0.25:gs=0.05:bs=-0.2,eq=saturation=1.25"},
    "lomo":       {"name": "LOMO", "ffmpeg": "vignette=PI/4,eq=saturation=1.4:contrast=1.1"},
    "polaroid":   {"name": "拍立得", "ffmpeg": "eq=saturation=0.85:brightness=0.08:contrast=0.9"},
    "grayscale_soft": {"name": "柔灰", "ffmpeg": "hue=s=0,gblur=sigma=0.6,eq=contrast=1.02"},
    "hdr":        {"name": "HDR", "ffmpeg": "unsharp=5:5:1.0,eq=saturation=1.35:contrast=1.25"},
    "pastel":     {"name": "粉彩", "ffmpeg": "eq=saturation=0.7:brightness=0.09,colorbalance=rs=0.1:bs=0.1"},
    "cinema21":   {"name": "电影宽屏", "ffmpeg": "eq=contrast=1.15:saturation=1.05,crop=iw:ih*0.82:0:ih*0.09"},
    "glitch":     {"name": "故障", "ffmpeg": "hue=h=20:s=1.5,eq=contrast=1.2,noise=alls=8:allf=t+u"},
    "blur_soft":  {"name": "柔焦", "ffmpeg": "gblur=sigma=2,eq=brightness=0.03"},
    "sharpen":    {"name": "锐化", "ffmpeg": "unsharp=5:5:0.8"},
    "invert":     {"name": "反色", "ffmpeg": "negate"},
    "vignette":   {"name": "暗角", "ffmpeg": "vignette=PI/3.2"},
    "golden":     {"name": "金秋", "ffmpeg": "colortemperature=temperature=5800,colorbalance=rs=0.12:gs=0.02,eq=saturation=1.2"},
    "cyberpunk":  {"name": "赛博", "ffmpeg": "hue=h=8,eq=saturation=1.7:contrast=1.2,colorbalance=bs=0.2:rs=-0.05"},
}

STICKERS: dict[str, dict] = {
    "heart":  {"name": "爱心", "emoji": "❤️"},
    "star":   {"name": "星星", "emoji": "⭐"},
    "fire":   {"name": "火焰", "emoji": "🔥"},
    "crown":  {"name": "皇冠", "emoji": "👑"},
    "money":  {"name": "招财", "emoji": "💰"},
    "music":  {"name": "音符", "emoji": "🎵"},
    "zap":    {"name": "闪电", "emoji": "⚡"},
    "rocket": {"name": "火箭", "emoji": "🚀"},
}

TRANSITIONS: dict[str, str] = {
    "fade":     "fade",
    "crossfade": "xfade=transition=fade",
    "wipeleft": "xfade=transition=wipeleft",
    "wiperight": "xfade=transition=wiperight",
    "slideup":  "xfade=transition=slideup",
    "circleopen": "xfade=transition=circleopen",
    "smoothup": "xfade=transition=smoothup",
    "dissolve": "xfade=transition=dissolve",
    "pixelize": "xfade=transition=pixelize",
}


def filter_list() -> list[dict]:
    return [{"id": k, "name": v["name"], "ffmpeg": v["ffmpeg"]} for k, v in FILTERS.items()]


def sticker_list() -> list[dict]:
    return [{"id": k, "name": v["name"], "emoji": v["emoji"]} for k, v in STICKERS.items()]


def transition_list() -> list[dict]:
    return [{"id": k, "name": k} for k in TRANSITIONS]
