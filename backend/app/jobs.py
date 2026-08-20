"""Async job manager: run engine tasks in background threads and persist status."""
from __future__ import annotations

import asyncio
import functools
import traceback
from typing import Any, Callable, Dict

from . import db


class JobManager:
    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()

    def start(self) -> None:
        # lazy start on first enqueue is handled by main lifespan
        pass

    async def enqueue(self, job_type: str, payload: Dict[str, Any], fn: Callable[..., Any]) -> str:
        job_id = db.create_job(job_type, payload)
        await self._queue.put((job_id, fn, payload))
        return job_id

    async def worker_loop(self) -> None:
        while True:
            job_id, fn, payload = await self._queue.get()
            db.update_job(job_id, status="running", progress=0.05)
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(None, functools.partial(self._run_sync, job_id, fn, payload))
                db.update_job(job_id, status="completed", progress=1.0, result=result)
            except Exception as exc:  # noqa: BLE001
                tb = traceback.format_exc()
                db.update_job(job_id, status="failed", progress=1.0, error={"message": str(exc), "trace": tb[-2000:]})
            finally:
                self._queue.task_done()

    @staticmethod
    def _run_sync(job_id: str, fn: Callable[..., Any], payload: Dict[str, Any]) -> Any:
        def report(progress: float, note: str = "") -> None:
            db.update_job(job_id, progress=float(progress))
            if note:
                db.update_job(job_id, result={"note": note})

        try:
            return fn(payload, report)
        except TypeError:
            return fn(payload)


manager = JobManager()
