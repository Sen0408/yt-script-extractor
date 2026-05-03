"""Fetch YouTube transcripts and (optionally) translate them.

Uses youtube-transcript-api, which pulls captions directly from YouTube and
can request YouTube's own auto-translation for any caption track.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)


@dataclass
class Script:
    video_id: str
    language: str
    language_name: str
    is_generated: bool
    is_translated: bool
    text: str
    segments: list[dict]


_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def video_id_from_url(url_or_id: str) -> str:
    """Accept a full YouTube URL or a bare 11-char video id."""
    if _YOUTUBE_ID_RE.match(url_or_id):
        return url_or_id

    parsed = urlparse(url_or_id)
    host = (parsed.hostname or "").lower()

    if host in {"<youtu.be>"}:
        vid = parsed.path.lstrip("/").split("/")[0]
        if _YOUTUBE_ID_RE.match(vid):
            return vid

    if "<youtube.com>" in host or "<youtube-nocookie.com>" in host:
        qs = parse_qs(parsed.query)
        if "v" in qs and _YOUTUBE_ID_RE.match(qs["v"][0]):
            return qs["v"][0]
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v"}:
            if _YOUTUBE_ID_RE.match(parts[1]):
                return parts[1]

    raise ValueError(f"Could not extract a YouTube video id from: {url_or_id!r}")


def _segments_to_text(segments: list[dict]) -> str:
    return "\n".join(seg["text"].strip() for seg in segments if seg.get("text"))


def fetch_original(video_id: str) -> Script:
    """Return the best-available original transcript. Manual > auto-generated."""
    try:
        listing = YouTubeTranscriptApi.list_transcripts(video_id)
    except TranscriptsDisabled as e:
        raise RuntimeError(f"Transcripts are disabled for video {video_id}.") from e

    manual = [t for t in listing if not t.is_generated]
    generated = [t for t in listing if t.is_generated]
    candidates = manual + generated
    if not candidates:
        raise RuntimeError(f"No transcripts available for video {video_id}.")

    transcript = candidates[0]
    segments = transcript.fetch()
    return Script(
        video_id=video_id,
        language=transcript.language_code,
        language_name=transcript.language,
        is_generated=transcript.is_generated,
        is_translated=False,
        text=_segments_to_text(segments),
        segments=segments,
    )


def fetch_translated(video_id: str, target_language: str) -> Script | None:
    """Translate to target_language via YouTube. None if already in that lang."""
    try:
        listing = YouTubeTranscriptApi.list_transcripts(video_id)
    except TranscriptsDisabled:
        return None

    manual = [t for t in listing if not t.is_generated]
    generated = [t for t in listing if t.is_generated]
    candidates = manual + generated
    if not candidates:
        return None

    source = candidates[0]
    if source.language_code == target_language:
        return None
    if not source.is_translatable:
        try:
            source = next(t for t in listing if t.is_translatable)
        except StopIteration:
            return None

    translated = source.translate(target_language)
    segments = translated.fetch()
    return Script(
        video_id=video_id,
        language=translated.language_code,
        language_name=translated.language,
        is_generated=source.is_generated,
        is_translated=True,
        text=_segments_to_text(segments),
        segments=segments,
    )


__all__ = [
    "Script",
    "fetch_original",
    "fetch_translated",
    "video_id_from_url",
    "NoTranscriptFound",
    "TranscriptsDisabled",
]
