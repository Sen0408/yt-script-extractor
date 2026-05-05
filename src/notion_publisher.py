"""Publish a video analysis as a Notion page under the configured parent page."""
from __future__ import annotations

import os

from .analyzer import Analysis
from .extractor import Script


def _client():
    from notion_client import Client
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise RuntimeError("NOTION_TOKEN is not set in .env")
    return Client(auth=token)


def _parent_page_id() -> str:
    pid = os.environ.get("NOTION_PARENT_PAGE_ID", "")
    if not pid:
        raise RuntimeError("NOTION_PARENT_PAGE_ID is not set in .env")
    return pid


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------

def _text(content: str, bold: bool = False) -> dict:
    ann = {"bold": bold}
    return {"type": "text", "text": {"content": content[:2000]}, "annotations": ann}


def _heading(level: int, content: str) -> dict:
    kind = f"heading_{level}"
    return {kind: {"rich_text": [_text(content)]}, "type": kind}


def _paragraph(content: str) -> list[dict]:
    """Split long text into ≤2000-char paragraph blocks."""
    blocks = []
    while content:
        chunk, content = content[:2000], content[2000:]
        blocks.append({
            "type": "paragraph",
            "paragraph": {"rich_text": [_text(chunk)]}
        })
    return blocks


def _bullet(content: str) -> dict:
    # Strip leading markdown bold markers for cleaner Notion rendering
    clean = content.lstrip("*").strip().lstrip("*").strip()
    # Split "bold title: explanation" into bold + normal
    if ": " in clean:
        bold_part, rest = clean.split(": ", 1)
        rich = [_text(bold_part + ": ", bold=True), _text(rest)]
    else:
        rich = [_text(clean)]
    # Truncate each rich_text item to 2000 chars
    for r in rich:
        r["text"]["content"] = r["text"]["content"][:2000]
    return {
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": rich}
    }


def _divider() -> dict:
    return {"type": "divider", "divider": {}}


def _callout(content: str, emoji: str = "🤖") -> list[dict]:
    """Callout block for AI Comments — splits into paragraphs if needed."""
    blocks = []
    first = True
    while content:
        chunk, content = content[:2000], content[2000:]
        if first:
            blocks.append({
                "type": "callout",
                "callout": {
                    "rich_text": [_text(chunk)],
                    "icon": {"type": "emoji", "emoji": emoji},
                    "color": "blue_background",
                }
            })
            first = False
        else:
            blocks.append({
                "type": "paragraph",
                "paragraph": {"rich_text": [_text(chunk)]}
            })
    return blocks


def _section_blocks(title: str, content: str, emoji: str = "") -> list[dict]:
    label = f"{emoji} {title}" if emoji else title
    blocks: list[dict] = [_divider(), _heading(2, label)]
    for para in content.split("\n\n"):
        para = para.strip().lstrip("#").strip().lstrip("*").strip("*").strip()
        if para:
            blocks.extend(_paragraph(para))
    return blocks


# ---------------------------------------------------------------------------
# Notion page builder
# ---------------------------------------------------------------------------

def _build_blocks(video_title: str, url: str, analysis: Analysis) -> list[dict]:
    blocks: list[dict] = []

    # Meta info
    blocks.extend(_paragraph(
        f"🔗 {url}\n"
        f"🌐 Language: {analysis.language}  |  "
        f"📝 Words: {analysis.word_count:,}  |  "
        f"⏱ Watch time: {analysis.estimated_watch_minutes} min  |  "
        f"🔬 Method: {analysis.method}"
    ))

    # Summary
    blocks += _section_blocks("Summary", analysis.summary, "📋")

    # Key Points
    blocks += [_divider(), _heading(2, "📌 Key Points")]
    for point in analysis.key_points:
        blocks.append(_bullet(point))

    # Deep Dive
    blocks += _section_blocks("Deep Dive", analysis.deep_dive, "🔍")

    # AI Comments — use callout blocks
    blocks += [_divider(), _heading(2, "🤖 AI Comments")]
    for para in analysis.ai_comments.split("\n\n"):
        para = para.strip().lstrip("#").strip().lstrip("*").strip("*").strip()
        if para:
            blocks += _callout(para)

    # Topics
    blocks += [_divider(), _heading(2, "🏷 Topics")]
    blocks.extend(_paragraph(", ".join(analysis.topics)))

    return blocks


def _push_blocks(client, page_id: str, blocks: list[dict]) -> None:
    """Append blocks in batches of 100 (Notion API limit)."""
    for i in range(0, len(blocks), 100):
        client.blocks.children.append(block_id=page_id, children=blocks[i:i+100])


# ---------------------------------------------------------------------------
# Transcript subpage
# ---------------------------------------------------------------------------

def _build_transcript_blocks(script: Script, url: str) -> list[dict]:
    blocks: list[dict] = []
    kind = "Whisper (auto-transcribed)" if "Whisper" in script.language_name else (
        "auto-generated" if script.is_generated else "uploader-provided"
    )
    blocks.extend(_paragraph(
        f"🔗 {url}\n"
        f"🌐 Language: {script.language_name} ({script.language})  |  Source: {kind}"
    ))
    blocks.append(_divider())
    for line in script.text.split("\n"):
        line = line.strip()
        if line:
            blocks.extend(_paragraph(line))
    return blocks


def _create_transcript_subpage(client, parent_page_id: str, script: Script, url: str) -> None:
    sub = client.pages.create(
        parent={"page_id": parent_page_id},
        properties={
            "title": {"title": [{"type": "text", "text": {"content": "📄 Original Transcript"}}]}
        },
    )
    blocks = _build_transcript_blocks(script, url)
    _push_blocks(client, sub["id"], blocks)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def publish(video_title: str, video_id: str, analysis: Analysis, script: Script) -> str:
    """Create a Notion child page with analysis + transcript subpage. Returns the page URL."""
    client = _client()
    parent_id = _parent_page_id()
    url = f"https://www.youtube.com/watch?v={video_id}"

    # 1. Create the main analysis page (empty)
    page = client.pages.create(
        parent={"page_id": parent_id},
        properties={
            "title": {"title": [{"type": "text", "text": {"content": video_title[:255]}}]}
        },
    )
    page_id = page["id"]

    # 2. Create transcript subpage first — appears at top of the page in Notion
    _create_transcript_subpage(client, page_id, script, url)

    # 3. Append analysis content below the subpage
    blocks = _build_blocks(video_title, url, analysis)
    _push_blocks(client, page_id, blocks)

    notion_url = page.get("url", f"https://www.notion.so/{page_id.replace('-', '')}")
    return notion_url


__all__ = ["publish"]
