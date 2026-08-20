"""Pydantic request/response models."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---- auth ----
class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    ok: bool
    message: str = ""


# ---- media ----
class MediaOut(BaseModel):
    id: str
    name: str
    path: str
    mime: str = ""
    size: int = 0
    duration: float = 0
    width: int = 0
    height: int = 0
    kind: str = "video"
    created_at: float = 0
    url: str = ""


# ---- edit ops ----
class TrimOp(BaseModel):
    start: float = 0.0
    end: Optional[float] = None
    duration: Optional[float] = None


class EditRequest(BaseModel):
    media_id: str
    ops: List[Dict[str, Any]] = Field(default_factory=list)
    export: Dict[str, Any] = Field(default_factory=dict)


class FilterPreset(BaseModel):
    id: str
    name: str
    description: str = ""


# ---- ai ----
class SubtitleRequest(BaseModel):
    media_id: str
    lang: str = "auto"
    model: str = "small"
    burn_in: bool = False
    style: Dict[str, Any] = Field(default_factory=dict)


class RemoveRequest(BaseModel):
    media_id: str
    mode: str = "background"  # background | object
    mask: Optional[Dict[str, Any]] = None
    provider: str = "local"


class AutoClipRequest(BaseModel):
    media_id: str
    mode: str = "highlights"  # highlights | scenes
    max_clips: int = 5
    min_clip_seconds: float = 1.0


class T2VRequest(BaseModel):
    prompt: str
    duration: float = 5.0
    size: str = "1280x720"
    orientation: str = "16:9"
    voiceover: Optional[str] = None
    lang: str = "auto"
    provider: str = "local"


# ---- api keys ----
class KeyCreate(BaseModel):
    name: str = "default"


class KeyOut(BaseModel):
    key: str
    name: str
    enabled: int
    created_at: float


# ---- openai format ----
class OpenAIVideoGenRequest(BaseModel):
    model: str = "filmora-t2v"
    prompt: str
    duration: Optional[float] = 5.0
    size: Optional[str] = "1280x720"
    orientation: Optional[str] = "16:9"
    voiceover: Optional[str] = None
    response_format: str = "url"
    n: int = 1


class OpenAIVideoEditRequest(BaseModel):
    model: str = "filmora-video-edit"
    video: Optional[str] = None  # url, base64 data uri, or uploaded file id
    prompt: Optional[str] = None
    image: Optional[str] = None
    ops: Optional[List[Dict[str, Any]]] = None
    response_format: str = "url"


class OpenAIError(BaseModel):
    error: Dict[str, Any]
