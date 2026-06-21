"""CLI entry point for yt-script-extractor.

Usage:
    python main.py <url-or-id> [--lang en] [--out ./scripts] [--format txt,docx]
"""
from __future__ import annotations

import argparse
import os
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
    p.add_argument("--lang", "-l", default="zh-Hans",
                   help="Target translation language when --translate is used. Default: zh-Hans")
    p.add_argument("--out", "-o", default="scripts", type=Path,
                   help="Output directory. Default: ./scripts")
    p.add_argument("--format", "-f", default="txt,docx",
                   help="Comma-separated output formats: txt, docx. Default: txt,docx")
    p.add_argument("--no-timestamps", action="store_true",
                   help="Omit per-line timestamps in the output files.")
    p.add_argument("--translate", action="store_false", dest="skip_translation",
                   help="Also save a YouTube auto-translated transcript.")
    p.add_argument("--skip-translation", action="store_true", default=True,
                   help="Only save the original-language transcript (default).")
    p.add_argument("--analyze", "-a", action="store_true", default=True,
                   help="Run analysis (default).")
    p.add_argument("--no-analyze", action="store_false", dest="analyze",
                   help="Skip analysis.")
    p.add_argument("--notion", "-n", action="store_true", default=True,
                   help="Publish analysis to Notion (default).")
    p.add_argument("--no-notion", action="store_false", dest="notion",
                   help="Skip Notion publishing.")
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
    if args.notion and not args.analyze:
        print("ERROR: Notion publishing requires analysis. Use --no-notion too.", file=sys.stderr)
        return 2
    if args.notion:
        missing = [k for k in ("NOTION_TOKEN", "NOTION_PARENT_PAGE_ID") if not os.environ.get(k)]
        if missing:
            print(
                "ERROR: Notion publishing is enabled by default, but these .env "
                f"values are missing: {', '.join(missing)}. "
                "Add them or use --no-notion.",
                file=sys.stderr,
            )
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
        from src.library import upsert_video
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

        notion_url = None
        if args.notion:
            from src.notion_publisher import publish
            print(f"      publishing to Notion...")
            try:
                notion_url = publish(title, video_id, analysis, original)
                print(f"      notion: {notion_url}")
            except Exception as e:
                print(f"      ERROR (Notion): {e}", file=sys.stderr)
        upsert_video(
            title,
            original,
            analysis,
            notion_url=notion_url,
            folder_path=out_dir,
        )
        print(f"      app library: saved")
        step += 1

    print(f"\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
