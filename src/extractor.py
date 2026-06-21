"""Fetch YouTube transcripts and (optionally) translate them.

Uses youtube-transcript-api, which pulls captions directly from YouTube and
can request YouTube's own auto-translation for any caption track.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import opencc
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
from youtube_transcript_api._errors import TranslationLanguageNotAvailable

# When YouTube doesn't offer a Simplified Chinese track, fall back to
# Traditional Chinese and convert with OpenCC.
_ZH_SIMP_FALLBACKS: dict[str, tuple[str, str, str]] = {
    "zh-Hans": ("zh-Hant", "Chinese (Simplified)", "t2s"),
    "zh-CN":   ("zh-TW",   "Chinese (Simplified)", "t2s"),
}


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

    if host in {"youtu.be"}:
        vid = parsed.path.lstrip("/").split("/")[0]
        if _YOUTUBE_ID_RE.match(vid):
            return vid

    if "youtube.com" in host or "youtube-nocookie.com" in host:
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


def _fetched_to_segments(fetched) -> list[dict]:
    return [
        {"text": s.text, "start": s.start, "duration": s.duration}
        for s in fetched
    ]


def fetch_video_title(video_id: str) -> str:
    """Return the video title from the YouTube page. Falls back to video_id."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "--skip-download",
                "--no-warnings",
                "--print",
                "title",
                f"https://www.youtube.com/watch?v={video_id}",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        title = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if result.returncode == 0 and title:
            return title
    except Exception:
        pass

    import urllib.request
    url = f"https://www.youtube.com/watch?v={video_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'"title":"([^"]+)"', html)
        if m:
            return m.group(1)
    except Exception:
        pass
    return video_id


def fetch_original(video_id: str, whisper_model: str = "base") -> Script:
    """Return the best-available original transcript. Falls back to Whisper if captions are disabled."""
    try:
        listing = YouTubeTranscriptApi().list(video_id)
    except TranscriptsDisabled:
        from .transcriber import transcribe_video
        print(f"      captions disabled — falling back to Whisper transcription")
        return transcribe_video(video_id, model=whisper_model)

    manual = [t for t in listing if not t.is_generated]
    generated = [t for t in listing if t.is_generated]
    candidates = manual + generated
    if not candidates:
        raise RuntimeError(f"No transcripts available for video {video_id}.")

    transcript = candidates[0]
    fetched = transcript.fetch()
    segments = _fetched_to_segments(fetched)
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
        listing = YouTubeTranscriptApi().list(video_id)
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

    try:
        translated = source.translate(target_language)
        lang_code = translated.language_code
        lang_name = translated.language
        fetched = translated.fetch()
        segments = _fetched_to_segments(fetched)
    except TranslationLanguageNotAvailable:
        fallback = _ZH_SIMP_FALLBACKS.get(target_language)
        if fallback is None:
            raise
        fallback_lang, lang_name, opencc_cfg = fallback
        translated = source.translate(fallback_lang)
        fetched = translated.fetch()
        segments = _fetched_to_segments(fetched)
        converter = opencc.OpenCC(opencc_cfg)
        for seg in segments:
            seg["text"] = converter.convert(seg["text"])
        lang_code = target_language
        print(f"      '{target_language}' not available via YouTube; "
              f"converted from '{fallback_lang}' using OpenCC")

    return Script(
        video_id=video_id,
        language=lang_code,
        language_name=lang_name,
        is_generated=source.is_generated,
        is_translated=True,
        text=_segments_to_text(segments),
        segments=segments,
    )


__all__ = [
    "Script",
    "fetch_original",
    "fetch_translated",
    "fetch_video_title",
    "video_id_from_url",
    "NoTranscriptFound",
    "TranscriptsDisabled",
]
