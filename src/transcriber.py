"""Fallback transcription via yt-dlp + Whisper for videos with captions disabled."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .extractor import Script


_FFMPEG_FALLBACK = (
    r"C:\Users\bsncu\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\ffmpeg-8.1-full_build\bin"
)


def _ffmpeg_available() -> bool:
    if shutil.which("ffmpeg"):
        return True
    ffmpeg_path = Path(_FFMPEG_FALLBACK) / "ffmpeg.exe"
    if ffmpeg_path.exists():
        os.environ["PATH"] = str(Path(_FFMPEG_FALLBACK)) + os.pathsep + os.environ.get("PATH", "")
        return True
    return False


def _download_audio_pytubefix(video_id: str, out_path: Path) -> Path:
    from pytubefix import YouTube
    yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
    stream = yt.streams.get_audio_only()
    if stream is None:
        raise RuntimeError("No audio stream found via pytubefix.")
    downloaded = stream.download(output_path=str(out_path), filename="audio_raw")
    return Path(downloaded)


def _download_audio_ytdlp(video_id: str, out_path: Path) -> Path:
    url = f"https://www.youtube.com/watch?v={video_id}"
    audio_file = out_path / "audio"
    cmd = [
        sys.executable, "-m", "yt_dlp", "--no-playlist",
        "-x", "--audio-format", "mp3", "--audio-quality", "5",
        "-o", str(audio_file) + ".%(ext)s",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "Only images are available" in stderr or "Requested format is not available" in stderr:
            raise RuntimeError(
                "No audio stream available. The video may be age-restricted, "
                "region-locked, or YouTube is rate-limiting downloads."
            )
        raise RuntimeError(f"yt-dlp failed: {stderr}")
    candidates = list(out_path.glob("audio.*"))
    if not candidates:
        raise RuntimeError("yt-dlp produced no audio file.")
    return candidates[0]


def _download_audio(video_id: str, out_path: Path) -> Path:
    try:
        return _download_audio_pytubefix(video_id, out_path)
    except Exception as e:
        print(f"      pytubefix failed ({e}), trying yt-dlp...")
        return _download_audio_ytdlp(video_id, out_path)


def _transcribe(audio_path: Path, model_name: str = "base") -> list[dict]:
    import whisper
    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path), word_timestamps=False, fp16=False)
    segments = []
    for seg in result["segments"]:
        segments.append({
            "text": seg["text"].strip(),
            "start": seg["start"],
            "duration": seg["end"] - seg["start"],
        })
    return segments, result.get("language", "en")


def transcribe_video(video_id: str, model: str = "base") -> Script:
    """Download audio and transcribe with Whisper. Returns a Script compatible with the rest of the pipeline."""
    if not _ffmpeg_available():
        raise RuntimeError(
            "ffmpeg is not installed or not on PATH. "
            "Install it from https://ffmpeg.org or via: winget install ffmpeg"
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        print(f"      downloading audio...")
        audio_path = _download_audio(video_id, tmp_path)
        print(f"      transcribing with Whisper ({model})...")
        segments, lang = _transcribe(audio_path, model)

    text = "\n".join(s["text"] for s in segments if s.get("text"))
    return Script(
        video_id=video_id,
        language=lang,
        language_name=f"Whisper ({lang})",
        is_generated=True,
        is_translated=False,
        text=text,
        segments=segments,
    )


__all__ = ["transcribe_video"]
