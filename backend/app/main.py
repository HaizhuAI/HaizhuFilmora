"""Filmora WebUI — FastAPI application entry."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .jobs import manager
from .routers import ai, api_keys, auth, edit, media, openai_api

ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(manager.worker_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(media.router)
app.include_router(edit.router)
app.include_router(ai.router)
app.include_router(api_keys.router)
app.include_router(openai_api.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "app": "filmora-webui", "version": settings.VERSION,
            "t2v_provider": settings.T2V_PROVIDER}


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"message": str(exc.detail), "type": "api_error", "code": "api_error"}})


# ---- static assets / exports / jobs ----
app.mount("/exports", StaticFiles(directory=settings.EXPORT_DIR), name="exports")
app.mount("/jobs", StaticFiles(directory=settings.JOB_DIR), name="jobs")

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # api routes handled above; anything else -> SPA index (history fallback)
        candidate = (FRONTEND_DIST / full_path)
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"error": {"message": "前端未构建，请先构建 frontend/dist", "type": "not_found"}}, status_code=404)
