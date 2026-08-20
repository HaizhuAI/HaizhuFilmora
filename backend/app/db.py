"""SQLite persistence: media library, jobs, api keys."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from .config import settings

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _lock, _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                mime TEXT,
                size INTEGER DEFAULT 0,
                duration REAL DEFAULT 0,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                kind TEXT DEFAULT 'video',
                created_at REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT DEFAULT 'queued',
                progress REAL DEFAULT 0,
                payload TEXT,
                result TEXT,
                error TEXT,
                created_at REAL DEFAULT 0,
                finished_at REAL
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                key TEXT PRIMARY KEY,
                name TEXT,
                enabled INTEGER DEFAULT 1,
                created_at REAL DEFAULT 0
            );
            """
        )


def now() -> float:
    return time.time()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


# ---------------- media ----------------
def insert_media(rec: dict) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO media (id,name,path,mime,size,duration,width,height,kind,created_at) "
            "VALUES (:id,:name,:path,:mime,:size,:duration,:width,:height,:kind,:created_at)",
            rec,
        )


def get_media(media_id: str) -> Optional[dict]:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT * FROM media WHERE id=?", (media_id,)).fetchone()
        return dict(row) if row else None


def list_media(kind: Optional[str] = None) -> list[dict]:
    with _lock, _conn() as conn:
        if kind:
            rows = conn.execute(
                "SELECT * FROM media WHERE kind=? ORDER BY created_at DESC", (kind,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM media ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def delete_media(media_id: str) -> bool:
    with _lock, _conn() as conn:
        cur = conn.execute("DELETE FROM media WHERE id=?", (media_id,))
        return cur.rowcount > 0


# ---------------- jobs ----------------
def create_job(job_type: str, payload: dict) -> str:
    job_id = new_id("job_")
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO jobs (id,type,status,progress,payload,created_at) VALUES (?,?,?,?,?,?)",
            (job_id, job_type, "queued", 0.0, json.dumps(payload, ensure_ascii=False), now()),
        )
    return job_id


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    allowed = {"status", "progress", "result", "error", "finished_at"}
    sets = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k}=?")
        vals.append(json.dumps(v, ensure_ascii=False) if k in ("result", "error") else v)
    if not sets:
        return
    if fields.get("status") in ("completed", "failed", "cancelled"):
        sets.append("finished_at=?")
        vals.append(now())
    vals.append(job_id)
    with _lock, _conn() as conn:
        conn.execute(f"UPDATE jobs SET {','.join(sets)} WHERE id=?", vals)


def get_job(job_id: str) -> Optional[dict]:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def list_jobs(limit: int = 50) -> list[dict]:
    with _lock, _conn() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


# ---------------- api keys ----------------
def add_api_key(name: str = "default") -> str:
    key = "sk-" + uuid.uuid4().hex
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (key,name,enabled,created_at) VALUES (?,?,1,?)",
            (key, name, now()),
        )
    return key


def list_api_keys() -> list[dict]:
    with _lock, _conn() as conn:
        rows = conn.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def revoke_api_key(key: str) -> bool:
    with _lock, _conn() as conn:
        cur = conn.execute("DELETE FROM api_keys WHERE key=?", (key,))
        return cur.rowcount > 0


def is_valid_key(key: str) -> bool:
    if not key:
        return False
    with _lock, _conn() as conn:
        row = conn.execute("SELECT 1 FROM api_keys WHERE key=? AND enabled=1", (key,)).fetchone()
        return row is not None or key in settings.STATIC_API_KEYS
