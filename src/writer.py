"""Write a Script out as .txt and/or .docx."""
from __future__ import annotations

from pathlib import Path

from .extractor import Script


def _format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _header(script: Script) -> str:
    kind = "auto-generated" if script.is_generated else "uploader-provided"
    if script.is_translated:
        kind += ", translated by YouTube"
    return (
        f"YouTube video: <https://www.youtube.com/watch?v={script.video_id}\n>"
        f"Language: {script.language_name} ({script.language})\n"
        f"Source: {kind}\n"
        f"{'-' * 60}\n"
    )


def write_txt(script: Script, path: Path, with_timestamps: bool = True) -> Path:
    lines = [_header(script)]
    if with_timestamps:
        for seg in script.segments:
            ts = _format_timestamp(seg.get("start", 0))
            text = seg.get("text", "").strip()
            if text:
                lines.append(f"[{ts}] {text}")
    else:
        lines.append(script.text)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_docx(script: Script, path: Path, with_timestamps: bool = True) -> Path:
    try:
        from docx import Document
    except ImportError as e:
        raise RuntimeError(
            "python-docx is not installed. Run: pip install python-docx"
        ) from e

    doc = Document()
    doc.add_heading(f"Transcript - {script.video_id}", level=1)
    doc.add_paragraph(f"URL: <https://www.youtube.com/watch?v={script.video_id}>")
    doc.add_paragraph(f"Language: {script.language_name} ({script.language})")
    kind = "auto-generated" if script.is_generated else "uploader-provided"
    if script.is_translated:
        kind += ", translated by YouTube"
    doc.add_paragraph(f"Source: {kind}")
    doc.add_paragraph("")

    if with_timestamps:
        for seg in script.segments:
            ts = _format_timestamp(seg.get("start", 0))
            text = seg.get("text", "").strip()
            if text:
                doc.add_paragraph(f"[{ts}] {text}")
    else:
        doc.add_paragraph(script.text)

    doc.save(path)
    return path


def output_paths(out_dir: Path, script: Script, suffix: str) -> dict[str, Path]:
    """Return {format: path} for <video_id>_<suffix>_<lang>.<ext> files."""
    base = f"{script.video_id}_{suffix}_{script.language}"
    return {"txt": out_dir / f"{base}.txt", "docx": out_dir / f"{base}.docx"}
