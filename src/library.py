"""SQLite-backed video library shared by the CLI, API, and iOS app."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analyzer import Analysis
from .extractor import Script


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "video_library.sqlite3"
SCRIPTS_PATH = ROOT / "scripts"
_VIDEO_ID_RE = re.compile(r"\[([A-Za-z0-9_-]{11})\]$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                key_points_json TEXT NOT NULL DEFAULT '[]',
                deep_dive TEXT NOT NULL DEFAULT '',
                ai_comments TEXT NOT NULL DEFAULT '',
                topics_json TEXT NOT NULL DEFAULT '[]',
                transcript TEXT NOT NULL DEFAULT '',
                word_count INTEGER NOT NULL DEFAULT 0,
                watch_minutes REAL NOT NULL DEFAULT 0,
                analysis_method TEXT NOT NULL DEFAULT '',
                thumbnail_url TEXT NOT NULL DEFAULT '',
                notion_url TEXT,
                folder_path TEXT,
                status TEXT NOT NULL DEFAULT 'ready',
                is_favorite INTEGER NOT NULL DEFAULT 0,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                video_id TEXT,
                source_url TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def _row_to_video(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["key_points"] = json.loads(item.pop("key_points_json") or "[]")
    item["topics"] = json.loads(item.pop("topics_json") or "[]")
    item["is_favorite"] = bool(item["is_favorite"])
    item["is_read"] = bool(item["is_read"])
    return item


def upsert_video(
    title: str,
    script: Script,
    analysis: Analysis,
    *,
    notion_url: str | None = None,
    folder_path: Path | None = None,
) -> dict[str, Any]:
    initialize()
    now = _now()
    url = f"https://www.youtube.com/watch?v={script.video_id}"
    thumbnail = f"https://img.youtube.com/vi/{script.video_id}/hqdefault.jpg"
    with connect() as conn:
        existing = conn.execute(
            "SELECT created_at, is_favorite, is_read, notion_url FROM videos WHERE video_id = ?",
            (script.video_id,),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        favorite = existing["is_favorite"] if existing else 0
        is_read = existing["is_read"] if existing else 0
        notion = notion_url or (existing["notion_url"] if existing else None)
        conn.execute(
            """
            INSERT INTO videos (
                video_id, title, url, language, summary, key_points_json,
                deep_dive, ai_comments, topics_json, transcript, word_count,
                watch_minutes, analysis_method, thumbnail_url, notion_url,
                folder_path, status, is_favorite, is_read, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title=excluded.title,
                url=excluded.url,
                language=excluded.language,
                summary=excluded.summary,
                key_points_json=excluded.key_points_json,
                deep_dive=excluded.deep_dive,
                ai_comments=excluded.ai_comments,
                topics_json=excluded.topics_json,
                transcript=excluded.transcript,
                word_count=excluded.word_count,
                watch_minutes=excluded.watch_minutes,
                analysis_method=excluded.analysis_method,
                thumbnail_url=excluded.thumbnail_url,
                notion_url=COALESCE(excluded.notion_url, videos.notion_url),
                folder_path=excluded.folder_path,
                status='ready',
                updated_at=excluded.updated_at
            """,
            (
                script.video_id,
                title,
                url,
                analysis.language,
                analysis.summary,
                json.dumps(analysis.key_points, ensure_ascii=False),
                analysis.deep_dive,
                analysis.ai_comments,
                json.dumps(analysis.topics, ensure_ascii=False),
                script.text,
                analysis.word_count,
                analysis.estimated_watch_minutes,
                analysis.method,
                thumbnail,
                notion,
                str(folder_path) if folder_path else None,
                favorite,
                is_read,
                created_at,
                now,
            ),
        )
    return get_video(script.video_id)


def list_videos(
    *,
    query: str = "",
    favorite: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    initialize()
    clauses: list[str] = []
    values: list[Any] = []
    if query:
        clauses.append(
            "(title LIKE ? OR summary LIKE ? OR topics_json LIKE ? OR transcript LIKE ?)"
        )
        needle = f"%{query}%"
        values.extend([needle, needle, needle, needle])
    if favorite is not None:
        clauses.append("is_favorite = ?")
        values.append(1 if favorite else 0)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.extend([min(max(limit, 1), 500), max(offset, 0)])
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM videos
            {where}
            ORDER BY is_favorite DESC, updated_at DESC
            LIMIT ? OFFSET ?
            """,
            values,
        ).fetchall()
    return [_row_to_video(row) for row in rows]


def get_video(video_id: str) -> dict[str, Any]:
    initialize()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
    if row is None:
        raise KeyError(video_id)
    return _row_to_video(row)


def update_video_state(
    video_id: str,
    *,
    is_favorite: bool | None = None,
    is_read: bool | None = None,
    notion_url: str | None = None,
) -> dict[str, Any]:
    updates: list[str] = ["updated_at = ?"]
    values: list[Any] = [_now()]
    if is_favorite is not None:
        updates.append("is_favorite = ?")
        values.append(1 if is_favorite else 0)
    if is_read is not None:
        updates.append("is_read = ?")
        values.append(1 if is_read else 0)
    if notion_url is not None:
        updates.append("notion_url = ?")
        values.append(notion_url)
    values.append(video_id)
    with connect() as conn:
        cursor = conn.execute(
            f"UPDATE videos SET {', '.join(updates)} WHERE video_id = ?", values
        )
        if cursor.rowcount == 0:
            raise KeyError(video_id)
    return get_video(video_id)


def create_job(job_id: str, source_url: str, video_id: str | None = None) -> dict[str, Any]:
    initialize()
    now = _now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, video_id, source_url, status, message, created_at, updated_at)
            VALUES (?, ?, ?, 'queued', '', ?, ?)
            """,
            (job_id, video_id, source_url, now, now),
        )
    return get_job(job_id)


def update_job(
    job_id: str,
    *,
    status: str,
    message: str = "",
    video_id: str | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, message = ?, video_id = COALESCE(?, video_id), updated_at = ?
            WHERE job_id = ?
            """,
            (status, message, video_id, _now(), job_id),
        )
    return get_job(job_id)


def get_job(job_id: str) -> dict[str, Any]:
    initialize()
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(job_id)
    return dict(row)


def _split_analysis(text: str) -> dict[str, Any]:
    sections = {
        "SUMMARY": "",
        "KEY POINTS": "",
        "DEEP DIVE": "",
        "AI COMMENTS": "",
        "TOPICS": "",
    }
    current: str | None = None
    buffers = {key: [] for key in sections}
    for raw in text.splitlines():
        line = raw.strip()
        if line in sections:
            current = line
            continue
        if current and line and not set(line) <= {"-", "="}:
            buffers[current].append(line)
    key_points = [
        re.sub(r"^[•\-]\s*", "", line).strip()
        for line in buffers["KEY POINTS"]
        if line.startswith(("•", "-"))
    ]
    topics = [
        topic.strip()
        for topic in " ".join(buffers["TOPICS"]).split(",")
        if topic.strip()
    ]
    header = "\n".join(text.splitlines()[:8])
    language = re.search(r"Language:\s*(.+)", header)
    words = re.search(r"Word count:\s*([\d,]+)", header)
    minutes = re.search(r"Estimated watch time:\s*([\d.]+)", header)
    method = re.search(r"Analysis method:\s*(.+)", header)
    return {
        "language": language.group(1).strip() if language else "",
        "summary": "\n\n".join(buffers["SUMMARY"]),
        "key_points": key_points,
        "deep_dive": "\n\n".join(buffers["DEEP DIVE"]),
        "ai_comments": "\n\n".join(buffers["AI COMMENTS"]),
        "topics": topics,
        "word_count": int(words.group(1).replace(",", "")) if words else 0,
        "watch_minutes": float(minutes.group(1)) if minutes else 0,
        "method": method.group(1).strip() if method else "",
    }


def import_existing_scripts() -> int:
    """Import existing per-video folders into SQLite. Returns imported count."""
    initialize()
    if not SCRIPTS_PATH.exists():
        return 0
    imported = 0
    seen: set[str] = set()
    for folder in sorted(SCRIPTS_PATH.iterdir()):
        if not folder.is_dir():
            continue
        match = _VIDEO_ID_RE.search(folder.name)
        if not match:
            continue
        video_id = match.group(1)
        if video_id in seen:
            continue
        analyses = sorted(folder.glob("analysis_*.txt"))
        transcripts = sorted(folder.glob("original_*.txt"))
        if not analyses or not transcripts:
            continue
        seen.add(video_id)
        analysis_text = analyses[0].read_text(encoding="utf-8", errors="replace")
        transcript_text = transcripts[0].read_text(encoding="utf-8", errors="replace")
        parsed = _split_analysis(analysis_text)
        transcript_body = transcript_text.split("-" * 60, 1)[-1].strip()
        title = folder.name[: match.start()].strip() or video_id
        now = _now()
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO videos (
                    video_id, title, url, language, summary, key_points_json,
                    deep_dive, ai_comments, topics_json, transcript, word_count,
                    watch_minutes, analysis_method, thumbnail_url, folder_path,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title=excluded.title,
                    language=excluded.language,
                    summary=excluded.summary,
                    key_points_json=excluded.key_points_json,
                    deep_dive=excluded.deep_dive,
                    ai_comments=excluded.ai_comments,
                    topics_json=excluded.topics_json,
                    transcript=excluded.transcript,
                    word_count=excluded.word_count,
                    watch_minutes=excluded.watch_minutes,
                    analysis_method=excluded.analysis_method,
                    thumbnail_url=excluded.thumbnail_url,
                    folder_path=excluded.folder_path,
                    status='ready',
                    updated_at=excluded.updated_at
                """,
                (
                    video_id,
                    title,
                    f"https://www.youtube.com/watch?v={video_id}",
                    parsed["language"],
                    parsed["summary"],
                    json.dumps(parsed["key_points"], ensure_ascii=False),
                    parsed["deep_dive"],
                    parsed["ai_comments"],
                    json.dumps(parsed["topics"], ensure_ascii=False),
                    transcript_body,
                    parsed["word_count"],
                    parsed["watch_minutes"],
                    parsed["method"],
                    f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                    str(folder),
                    now,
                    now,
                ),
            )
        imported += 1
    return imported


__all__ = [
    "DB_PATH",
    "connect",
    "create_job",
    "get_job",
    "get_video",
    "import_existing_scripts",
    "initialize",
    "list_videos",
    "update_job",
    "update_video_state",
    "upsert_video",
]
