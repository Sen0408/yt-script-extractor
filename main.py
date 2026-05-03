"""CLI entry point for yt-script-extractor.

Usage:
    python main.py <url-or-id> [--lang en] [--out ./scripts] [--format txt,docx]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.extractor import fetch_original, fetch_translated, video_id_from_url
from src.writer import output_paths, write_docx, write_txt


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

    args.out.mkdir(parents=True, exist_ok=True)
    with_ts = not args.no_timestamps

    print(f"[1/3] Fetching original transcript for {video_id}...")
    try:
        original = fetch_original(video_id)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"      original language: {original.language_name} ({original.language})")
    saved = _save(original, "original", args.out, formats, with_ts)
    for p in saved:
        print(f"      saved {p}")

    if args.skip_translation or original.language == args.lang:
        if original.language == args.lang and not args.skip_translation:
            print(f"[2/3] Original is already in '{args.lang}'. Skipping translation.")
        print("[3/3] Done.")
        return 0

    print(f"[2/3] Translating to '{args.lang}' via YouTube...")
    translated = fetch_translated(video_id, args.lang)
    if translated is None:
        print(f"      no translatable track available for '{args.lang}'.")
    else:
        saved = _save(translated, args.lang, args.out, formats, with_ts)
        for p in saved:
            print(f"      saved {p}")

    print("[3/3] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
