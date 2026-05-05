"""Analyze a transcript — uses Claude API if key is available, else extractive NLP."""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass

from .extractor import Script

_STOPWORDS = {
    "a","about","above","after","again","all","also","an","and","any","are","as",
    "at","be","because","been","before","being","between","both","but","by","can",
    "did","do","does","doing","don","down","during","each","few","for","from",
    "further","get","go","had","has","have","having","he","her","here","him","his",
    "how","i","if","in","into","is","it","its","just","know","like","me","more",
    "most","my","no","not","now","of","on","one","only","or","other","our","out",
    "own","said","same","she","should","so","some","than","that","the","their",
    "them","then","there","these","they","this","those","through","to","too","up",
    "us","was","we","were","what","when","where","which","while","who","will",
    "with","would","you","your","going","want","okay","yeah","um","uh","actually",
    "just","really","very","well","right","got","let","see","make","made","say",
    "think","know","thing","things","way","use","can","get","take","give","come",
    "look","need","even","much","many","first","back","good","new","show","m",
    "re","ll","ve","s","t","d",
}


@dataclass
class Analysis:
    video_id: str
    language: str
    summary: str
    key_points: list[str]
    deep_dive: str
    ai_comments: str
    topics: list[str]
    word_count: int
    estimated_watch_minutes: float
    method: str  # "claude" or "extractive"


# ---------------------------------------------------------------------------
# Extractive fallback (no API key)
# ---------------------------------------------------------------------------

def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [s.strip() for s in parts if len(s.split()) > 4]


def _word_freq(text: str) -> Counter:
    words = re.findall(r"[a-z]+", text.lower())
    return Counter(w for w in words if w not in _STOPWORDS and len(w) > 2)


def _score_sentences(sentences: list[str], freq: Counter) -> list[tuple[float, str]]:
    scored = []
    for sent in sentences:
        words = re.findall(r"[a-z]+", sent.lower())
        score = sum(freq.get(w, 0) for w in words if w not in _STOPWORDS)
        if words:
            score /= math.sqrt(len(words))
        scored.append((score, sent))
    return scored


def _extractive_analyze(script: Script) -> Analysis:
    word_count = len(script.text.split())
    total_seconds = (
        script.segments[-1]["start"] + script.segments[-1].get("duration", 0)
        if script.segments else 0
    )
    watch_minutes = round(total_seconds / 60, 1)

    freq = _word_freq(script.text)
    sentences = _sentences(script.text)
    scored = sorted(_score_sentences(sentences, freq), reverse=True)

    top_sents = {s for _, s in scored[:5]}
    summary_sents = [s for s in sentences if s in top_sents][:5]
    mid = len(summary_sents) // 2
    para1 = " ".join(summary_sents[:mid]) if mid else " ".join(summary_sents)
    para2 = " ".join(summary_sents[mid:]) if mid else ""
    summary = "\n\n".join(p for p in [para1, para2] if p)

    key_points = [s if len(s) <= 120 else s[:117] + "..."
                  for _, s in scored if s not in top_sents][:8]
    topics = [word for word, _ in freq.most_common(6)]

    return Analysis(
        video_id=script.video_id,
        language=script.language,
        summary=summary,
        key_points=key_points,
        deep_dive="(Deep dive requires Claude API — set ANTHROPIC_API_KEY to enable.)",
        ai_comments="(AI comments require Claude API — set ANTHROPIC_API_KEY to enable.)",
        topics=topics,
        word_count=word_count,
        estimated_watch_minutes=watch_minutes,
        method="extractive",
    )


# ---------------------------------------------------------------------------
# Claude-powered analysis
# ---------------------------------------------------------------------------

_SYSTEM = """\
You are an expert content analyst and critical thinker. \
Given a YouTube video transcript, produce a comprehensive analytical report.

Respond in the SAME LANGUAGE as the transcript. \
Use EXACTLY the section headers below with no extra text outside them.

SUMMARY
Write 4–5 detailed paragraphs covering: the video's context and purpose, the main \
arguments or content presented, the evidence or examples used, how ideas develop \
through the video, and the conclusion or call to action.

KEY POINTS
List 8–10 bullet points. Each point should be a complete thought with a 1–2 sentence \
explanation of why it matters or what the viewer should take away. Format:
- <point>: <explanation>

DEEP DIVE
Write 3–4 paragraphs of in-depth analysis. Examine the quality of the main claims \
and reasoning. Evaluate what evidence or logic is presented. Identify any methodology, \
frameworks, or strategies discussed. Note what is well-explained and what is glossed \
over or left unsupported.

AI COMMENTS
Write 3–4 paragraphs of your own perspective as an AI analyst. Be direct and specific:
- What do you find compelling or well-argued, and why?
- What do you disagree with, find questionable, or think is oversimplified?
- What important context, counterpoints, or risks is the creator missing?
- What would you add, extend, or push back on?

TOPICS
List 6–10 topic tags as a comma-separated line.
"""


def _parse_response(text: str) -> tuple[str, list[str], str, str, list[str]]:
    sections: dict[str, list[str]] = {
        "SUMMARY": [], "KEY POINTS": [], "DEEP DIVE": [], "AI COMMENTS": [], "TOPICS": []
    }
    section = None
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip().strip("*").strip()
        if stripped in sections:
            section = stripped
        elif section and line.strip():
            sections[section].append(line.strip())

    summary = "\n\n".join(sections["SUMMARY"])

    key_points = []
    for line in sections["KEY POINTS"]:
        if line.startswith("- "):
            key_points.append(line[2:].strip())

    deep_dive = "\n\n".join(sections["DEEP DIVE"])
    ai_comments = "\n\n".join(sections["AI COMMENTS"])
    topics = [t.strip() for t in " ".join(sections["TOPICS"]).split(",") if t.strip()]

    return summary, key_points, deep_dive, ai_comments, topics


def _claude_analyze(script: Script) -> Analysis:
    import anthropic

    word_count = len(script.text.split())
    total_seconds = (
        script.segments[-1]["start"] + script.segments[-1].get("duration", 0)
        if script.segments else 0
    )
    watch_minutes = round(total_seconds / 60, 1)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": script.text[:20000]}],
    )
    summary, key_points, deep_dive, ai_comments, topics = _parse_response(
        response.content[0].text
    )

    return Analysis(
        video_id=script.video_id,
        language=script.language,
        summary=summary,
        key_points=key_points,
        deep_dive=deep_dive,
        ai_comments=ai_comments,
        topics=topics,
        word_count=word_count,
        estimated_watch_minutes=watch_minutes,
        method="claude",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze(script: Script) -> Analysis:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key.startswith("sk-ant-"):
        return _claude_analyze(script)
    return _extractive_analyze(script)


__all__ = ["Analysis", "analyze"]
