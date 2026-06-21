"""Local API consumed by the VideoBrief iOS app."""
from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.extractor import video_id_from_url
from src.library import (
    create_job,
    get_job,
    get_video,
    import_existing_scripts,
    initialize,
    list_videos,
    update_job,
    update_video_state,
)


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

app = FastAPI(title="VideoBrief API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_remote_token(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    expected = os.environ.get("VIDEOBRIEF_API_TOKEN", "")
    hostname = (request.url.hostname or "").lower()
    local_hosts = {
        "127.0.0.1",
        "localhost",
        "10.20.16.23",
        "sens-mac-mini.local",
        "sens-mac-mini.ad.analog.com",
    }
    is_local = hostname in local_hosts
    provided = request.headers.get("X-VideoBrief-Token", "")

    if expected and not is_local and not secrets.compare_digest(provided, expected):
        return JSONResponse(
            status_code=401,
            content={"detail": "VideoBrief access token required"},
        )
    return await call_next(request)


class ProcessVideoRequest(BaseModel):
    url: str = Field(min_length=5)
    translate: bool = False
    language: str = "zh-Hans"


class VideoStateRequest(BaseModel):
    is_favorite: bool | None = None
    is_read: bool | None = None


@app.on_event("startup")
def startup() -> None:
    initialize()
    import_existing_scripts()


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "VideoBrief API",
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "notion": bool(os.environ.get("NOTION_TOKEN")),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@app.get("/api/videos")
def videos(
    q: str = "",
    favorite: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    items = list_videos(query=q, favorite=favorite, limit=limit, offset=offset)
    return {"items": items, "count": len(items)}


@app.get("/api/videos/{video_id}")
def video(video_id: str) -> dict:
    try:
        return get_video(video_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Video not found") from None


@app.patch("/api/videos/{video_id}")
def patch_video(video_id: str, request: VideoStateRequest) -> dict:
    try:
        return update_video_state(
            video_id,
            is_favorite=request.is_favorite,
            is_read=request.is_read,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Video not found") from None


def _run_pipeline(job_id: str, request: ProcessVideoRequest, video_id: str) -> None:
    update_job(job_id, status="processing", message="正在提取字幕并生成解说", video_id=video_id)
    command = [
        sys.executable,
        str(ROOT / "main.py"),
        request.url,
        "--format",
        "txt,docx",
    ]
    if request.translate:
        command.extend(["--translate", "--lang", request.language])
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60 * 60,
            env=os.environ.copy(),
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode != 0:
            update_job(job_id, status="failed", message=output[-2000:], video_id=video_id)
            return
        import_existing_scripts()
        notion = re.search(r"notion:\s*(https?://\S+)", output)
        if notion:
            try:
                update_video_state(video_id, notion_url=notion.group(1))
            except KeyError:
                pass
        update_job(job_id, status="completed", message="解说已保存到 App 与 Notion", video_id=video_id)
    except Exception as exc:
        update_job(job_id, status="failed", message=str(exc), video_id=video_id)


@app.post("/api/videos/process", status_code=202)
def process_video(request: ProcessVideoRequest, background_tasks: BackgroundTasks) -> dict:
    try:
        video_id = video_id_from_url(request.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    job_id = uuid.uuid4().hex
    job = create_job(job_id, request.url, video_id)
    background_tasks.add_task(_run_pipeline, job_id, request, video_id)
    return job


@app.get("/api/jobs/{job_id}")
def job(job_id: str) -> dict:
    try:
        return get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None


@app.post("/api/library/import")
def import_library() -> dict:
    return {"imported": import_existing_scripts()}
