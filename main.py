"""CLI entry point for yt-script-extractor.

Usage:
    python main.py <url-or-id> [--lang en] [--out ./scripts] [--format txt,docx]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.extractor import fetch_original, fetch_translated, fetch_video_title, video_id_from_url
from src.writer import (
    output_paths,
    write_analysis_docx,
    write_analysis_txt,
    write_docx,
    write_txt,
)

_WIN_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_folder_name(title: str, video_id: str) -> str:
    sanitized = _WIN_INVALID.sub("", title).strip().strip(".")
    sanitized = re.sub(r"\s+", " ", sanitized)[:80].strip()
    return f"{sanitized} [{video_id}]" if sanitized else video_id


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="yt-script-extractor",
        description="Download a YouTube video's transcript in its original "
                    "language and an auto-translated version.",
    )
    p.add_argument("url", help="YouTube URL or 11-character video id")
    p.add_argument("--lang", "-l", default="en",
                   help="Target translation language (ISO code). Default: en")
    p.add_argument("--out", "-o", default="scripts", type=Path,
                   help="Output directory. Default: ./scripts")
    p.add_argument("--format", "-f", default="txt,docx",
                   help="Comma-separated output formats: txt, docx. Default: txt,docx")
    p.add_argument("--no-timestamps", action="store_true",
                   help="Omit per-line timestamps in the output files.")
    p.add_argument("--skip-translation", action="store_true",
                   help="Only save the original-language transcript.")
    p.add_argument("--analyze", "-a", action="store_true",
                   help="Run Claude analysis (summary, key points, topics).")
    p.add_argument("--notion", "-n", action="store_true",
                   help="Publish analysis to Notion. Requires --analyze and NOTION_TOKEN.")
    p.add_argument("--whisper-model", default="base",
                   choices=["tiny", "base", "small", "medium", "large"],
                   help="Whisper model for fallback transcription. Default: base")
    return p.parse_args(argv)


def _save(script, suffix, out_dir, formats, with_ts):
    paths = output_paths(out_dir, script, suffix)
    written = []
    if "txt" in formats:
        written.append(write_txt(script, paths["txt"], with_timestamps=with_ts))
    if "docx" in formats:
        written.append(write_docx(script, paths["docx"], with_timestamps=with_ts))
    return written


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    formats = {f.strip().lower() for f in args.format.split(",") if f.strip()}
    unknown = formats - {"txt", "docx"}
    if unknown:
        print(f"Unknown format(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    try:
        video_id = video_id_from_url(args.url)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    # --- fetch title + original first so we know whether to skip translation ---
    print(f"Fetching '{video_id}'...")
    title = fetch_video_title(video_id)
    folder_name = _safe_folder_name(title, video_id)
    out_dir = args.out / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        original = fetch_original(video_id, whisper_model=args.whisper_model)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    skip_translation = args.skip_translation or original.language == args.lang
    total = 1 + (not skip_translation) + args.analyze
    step = 1
    with_ts = not args.no_timestamps

    print(f"\n{title}")
    print(f"Folder: {out_dir}\n")

    print(f"[{step}/{total}] Original transcript ({original.language_name})...")
    saved = _save(original, "original", out_dir, formats, with_ts)
    for p in saved:
        print(f"      saved {p}")
    step += 1

    translated = None
    if not skip_translation:
        print(f"[{step}/{total}] Translating to '{args.lang}'...")
        try:
            translated = fetch_translated(video_id, args.lang)
        except Exception as e:
            print(f"      ERROR: {e}", file=sys.stderr)
            translated = None
        if translated is None:
            print(f"      no translatable track available for '{args.lang}'.")
        else:
            saved = _save(translated, args.lang, out_dir, formats, with_ts)
            for p in saved:
                print(f"      saved {p}")
        step += 1

    if args.analyze:
        from src.analyzer import analyze
        target_script = original  # always analyze original; translated is for reading only
        print(f"[{step}/{total}] Analyzing ({target_script.language})...")
        try:
            analysis = analyze(target_script)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        base = f"analysis_{target_script.language}"
        if "txt" in formats:
            p = write_analysis_txt(analysis, out_dir / f"{base}.txt")
            print(f"      saved {p}")
        if "docx" in formats:
            try:
                p = write_analysis_docx(analysis, out_dir / f"{base}.docx")
                print(f"      saved {p}")
            except PermissionError:
                print(f"      skipped .docx (file is open in another program)")
        print(f"      topics: {', '.join(analysis.topics)}")

        if args.notion:
            from src.notion_publisher import publish
            print(f"      publishing to Notion...")
            try:
                notion_url = publish(title, video_id, analysis, original)
                print(f"      notion: {notion_url}")
            except Exception as e:
                print(f"      ERROR (Notion): {e}", file=sys.stderr)
        step += 1

    print(f"\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
