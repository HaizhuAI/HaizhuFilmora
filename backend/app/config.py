"""Central configuration loaded from environment with sensible defaults."""
from __future__ import annotations

import os
import secrets
from pathlib import Path


def _root() -> Path:
    # backend/app/config.py -> project root (filmora-webui)
    return Path(__file__).resolve().parent.parent.parent


class Settings:
    def __init__(self) -> None:
        root = _root()
        self.PROJECT_NAME = "Filmora WebUI — AI Video Workstation"
        self.VERSION = "1.0.0"

        # --- security ---
        self.ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
        self.SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
        self.SESSION_COOKIE = "filmora_session"
        self.SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "72"))

        # --- runtime dirs ---
        data_dir = Path(os.getenv("DATA_DIR", str(root / "data")))
        self.DATA_DIR = data_dir
        self.UPLOAD_DIR = data_dir / "uploads"
        self.JOB_DIR = data_dir / "jobs"
        self.EXPORT_DIR = data_dir / "exports"
        self.DB_PATH = data_dir / "db" / "filmora.db"
        for d in (self.UPLOAD_DIR, self.JOB_DIR, self.EXPORT_DIR, self.DB_PATH.parent):
            d.mkdir(parents=True, exist_ok=True)

        # --- service ---
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", "8000"))
        self.MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "2048"))

        # --- api keys ---
        # static keys from env (comma separated); dynamic keys stored in DB
        self.STATIC_API_KEYS = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}

        # --- AI / provider ---
        # t2v engine: "local" (built-in generator) or "openai" (external OpenAI-compatible video API)
        self.T2V_PROVIDER = os.getenv("T2V_PROVIDER", "local")
        self.T2V_API_BASE = os.getenv("T2V_API_BASE", "")
        self.T2V_API_KEY = os.getenv("T2V_API_KEY", "")
        self.T2V_MODEL = os.getenv("T2V_MODEL", "filmora-t2v")
        self.EDIT_MODEL = os.getenv("EDIT_MODEL", "filmora-video-edit")

        # whisper / subtitles
        self.WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
        self.WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
        self.WHISPER_LANG = os.getenv("WHISPER_LANG", "auto")

        # export defaults
        self.EXPORT_CRF = int(os.getenv("EXPORT_CRF", "20"))
        self.FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
        self.FFPROBE_BIN = os.getenv("FFPROBE_BIN", "ffprobe")

    @property
    def public_base_url(self) -> str:
        return os.getenv("PUBLIC_BASE_URL", f"http://127.0.0.1:{self.PORT}").rstrip("/")


settings = Settings()
